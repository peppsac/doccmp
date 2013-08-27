#!/usr/bin/python

import sys
import os
import shutil
import hashlib
import time
import glob
from PIL import Image
import commands
import tempfile

libreoffice='/media/pierre-eric/309451c6-b1c2-4554-99a1-30452150b211/libreoffice-master/install/program/soffice'

im_command='convert -density 150 {} -background white -alpha Background -alpha off {}'
compare_command='compare -metric NCC  {} {} null'
resize_command='convert -resize {}x{} {} {}'

def create_folder_hierarchy_in(folder):
    os.makedirs(folder + '/O.W')
    os.makedirs(folder + '/O.L')
    os.makedirs(folder + '/O.L.L')
    os.makedirs(folder + '/O.L.O')


def print_to_pdf_from_word(filename, output_folder):
    print ("##############################################")
    print (" print_to_pdf_from_word: '%s'" % filename)

    # Build command (using implicitely joined strings)
    # SaveAsPDF2 is a macro saving the document to ~/PDF/eee.pdf
    command = ('wine "/home/pierre-eric/.wine/drive_c/Program Files (x86)/Microsoft Office/Office12/WINWORD.EXE" '
            '/q /t "z:' + filename +
            '" /mSaveAsPDF2 /mFileExit')

    # Execute command
    os.system(command)

    # Get filename
    fullname, ext = os.path.splitext(filename)
    basename = os.path.basename(filename).replace(ext, '.pdf')

    # Move file
    shutil.copy2("/home/pierre-eric/PDF/eee.pdf", output_folder + basename)
    os.remove("/home/pierre-eric/PDF/eee.pdf")

def print_to_pdf_from_libreoffice(filename, output_folder):
    print ("##############################################")
    print ("print_to_pdf_from_libreoffice: '%s'" % filename)

    # Build command (using implicitely joined strings)
    command = (libreoffice + ' --headless --convert-to pdf --outdir ' + output_folder + ' ' + filename)

    # Execute command
    os.system(command)

def print_to_docx_from_libreoffice(filename, output_folder):
    print ("##############################################")
    print (" print_to_docx_from_libreoffice: '%s'" % filename)

    command = (libreoffice + ' --headless --convert-to docx --outdir ' + output_folder + ' ' + filename)

    # Execute command
    os.system(command)

def init_document_compare(absolute_path, outdir):
    try:
        with open(absolute_path): pass
    except IOError:
        print "File '%s' doesn't exist. Aborting" % absolute_path
        return -1.

    filename = os.path.basename(absolute_path)

    # First, we need a id for this file
    file_id = hashlib.md5(open(absolute_path, 'rb').read()).hexdigest()
    full_path = outdir + file_id + '/'

    # Create folder
    if not os.path.exists(full_path):
        os.makedirs(full_path)
        create_folder_hierarchy_in(full_path)
        
    # Copy file to folder
    shutil.copy2(absolute_path, full_path)

    return filename, file_id

def generate_pdf_for_doc(filename, file_id, outdir):
    full_path = outdir + file_id + '/'

    # Generate PDF from Word
    print_to_pdf_from_word(full_path + filename, full_path + '/O.W/')

    # Import in LibreOffice and print to pdf
    print_to_pdf_from_libreoffice(full_path + filename, full_path + '/O.L/')

    # Import in LibreOffice, save as docx...
    print_to_docx_from_libreoffice(full_path + filename, full_path + '/O.L/')
    # ...then reopen and print to pdf from LibreOffice
    print_to_pdf_from_libreoffice(full_path + '/O.L/' + filename, full_path + '/O.L.L/')

    # Then print to pdf from Word
    print_to_pdf_from_word(full_path + '/O.L/' + filename, full_path + '/O.L.O/')

def generate_fullres_images_from_pdf(filename, file_id, outdir):
    full_path = outdir + file_id + '/'

    # Generate full resolution images from pdf
    filename_pdf = filename.replace('.docx', '.pdf')
    filename_png = filename.replace('.docx', '.png')
    for folder in ['O.W', 'O.L', 'O.L.L', 'O.L.O']:
        cmd = im_command.format(
            full_path + '/' + folder + '/' + filename_pdf,
            full_path + '/' + folder + '/' + filename_png)
        os.system(cmd)

def compare_pdf_using_images(filename, file_id, outdir):
    full_path = outdir + file_id + '/'

    total_scores = []
    sum_score = [0.0, 0.0, 0.0]
    single_pages = glob.glob(full_path + '/O.W/*.png')

    # Browse full resolution images (1 per page)
    for single_page_png in single_pages:
        im = Image.open(single_page_png)
        width, height = im.size

        images = [single_page_png]

        tmp_folder = tempfile.mkdtemp()
        create_folder_hierarchy_in(tmp_folder)

        # Generate all mipmaps in temp folder
        while width > 10 or height > 10:
            width = int(width / 2)
            height = int(height / 2)
            # oooh
            name = tmp_folder + '/O.W/' + os.path.basename(single_page_png).replace('.png', '_' + str(width) + 'x' + str(height) + '.png')
            # Execute IM resize command
            os.system(resize_command.format(width, height, single_page_png, name))
            # Add that to the list of images to be compared
            images += [name]

            for folder in ['O.L', 'O.L.L', 'O.L.O']:
                # Look up corresponding image in this folder
                full_path = single_page_png.replace('O.W', folder)
                if not os.path.exists(full_path):
                    continue
                # If present, execute IM resize command 
                os.system(resize_command.format(width, height, full_path, name.replace('O.W', folder)))

        # Compare mipmap
        folders = ['O.L', 'O.L.L', 'O.L.O']
        score = [0.0, 0.0, 0.0]
        steps = 1

        for image in images:
            for i in range(0, len(folders)):
                folder = folders[i]
                image2 = image.replace('O.W', folder)

                if not os.path.exists(image2):
                    print ("%s doesn't exist" % image2)
                    continue

                result, value = commands.getstatusoutput(compare_command.format(image, image2))
                if result == 0:
                    print ("Compare: %s and %s -> %s (%f)" % (image, image2, value, min(1.0, float(value))))
                    score[i] += min(1.0, float(value)) * steps
        
            steps = steps + 1

        for i in range(0, len(folders)):
            score[i] = score[i] / sum(range(1, steps))
            sum_score[i] = sum_score[i] + score[i]


        # remove temp dir
        shutil.rmtree(tmp_folder)

        total_scores += [score]

    for i in range(0, len(sum_score)):
        sum_score[i] = sum_score[i] / float(len(single_pages))

    print ("FINAL SCORE: " + str(sum_score))

    return sum_score, len(single_pages)


if __name__ == "__main__":
    count = len(sys.argv)
    if count > 1:
        outdir = '/tmp/document_compare/'
        for i in range(1, len(sys.argv)):
            filename, file_id = init_document_compare (sys.argv[i], outdir)
            generate_pdf_for_doc(filename, file_id, outdir)
            generate_fullres_images_from_pdf(filename, file_id, outdir)
            compare_pdf_using_images(filename, file_id, outdir)