# Copyright 2009 One Laptop Per Child
# Author: Sayamindu Dasgupta <sayamindu@laptop.org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import gobject
import webkit
import gtk
import os.path, shutil, time, sys, tempfile

from pyPdf import PdfFileWriter, PdfFileReader

from epubview import Epub

gobject.threads_init()

def append_pdf(input,output): 
    [output.addPage(input.getPage(page_num)) for page_num in range(input.numPages)]  

def load_finished_cb(view, frame, output):
    f = view.get_main_frame()
    printop = gtk.PrintOperation()
    opn = gtk.PRINT_OPERATION_ACTION_EXPORT
    printop.set_export_filename(output)
    f.print_full(printop, opn)

    pdf = PdfFileWriter()

    if os.path.exists(sys.argv[2]):
        fobj = file(sys.argv[2], 'rb')
        append_pdf(PdfFileReader(fobj), pdf)
    else:
        fobj = None

    ifobj = file(output, 'rb')
    append_pdf(PdfFileReader(ifobj), pdf)

    filename = str(time.time()) + '.pdf'
    ofobj = file(filename, 'wb')
    pdf.write(ofobj)
    ofobj.close()

    if fobj:
        fobj.close()
    
    ifobj.close()

    shutil.move(filename, sys.argv[2])

    gtk.main_quit()

def gen_pdf(file, output):
    win = gtk.Window()
    view = webkit.WebView()
    settings = webkit.WebSettings()
    settings.props.default_encoding = 'utf-8'
    settings.props.enforce_96_dpi = True
    settings.props.default_font_family = 'DejaVu LGC Serif'
    settings.props.enable_plugins = False
    settings.props.enable_scripts = False    
    view.set_settings(settings)
    view.connect('load-finished', load_finished_cb, output)
    view.open(file)

    win.add(view)
    win.set_size_request(1024, 768) #This is to get the image rendering right

    win.show_all()
    win.unrealize()

    gtk.main()

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print ('Usage: %s <infilename> <outfilename>' % sys.argv[0]) 
    
    epub = Epub(sys.argv[1])
    
    tempdir = tempfile.mkdtemp()
    
    if os.path.exists(sys.argv[2]):
        os.remove(sys.argv[2])
    
    for item in epub.get_flattoc():
        filename = os.path.join(epub.get_basedir(), item[1])
        gen_pdf(filename, os.path.join(tempdir, os.path.basename(item[1])))
    
    shutil.rmtree(tempdir)