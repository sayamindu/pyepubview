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
import gtk
import webkit

import math
import os.path
import BeautifulSoup

import epub

PAGE_WIDTH = 135
PAGE_HEIGHT = 216

def _pixel_to_mm(pixel, dpi):
    inches = pixel/dpi
    return int(inches/0.03937)

def _mm_to_pixel(mm, dpi):
    inches = mm * 0.03937
    return int(inches * dpi)

class _JobPaginator(gobject.GObject):
    __gsignals__ = {
        'paginated': (gobject.SIGNAL_RUN_FIRST,
                          gobject.TYPE_NONE,
                          ([]))
    }   
    def __init__(self, filelist):
        gobject.GObject.__init__(self)
        
        self._filelist = filelist
        self._filedict = {}
        self._pagemap = {}
        
        self._bookheight = 0
        self._count = 0
        self._pagecount = 0
        
        self._temp_win = gtk.Window()
        self._temp_view = webkit.WebView()

        settings = self._temp_view.get_settings()
        settings.props.default_font_family = 'DejaVu LGC Serif'
        settings.props.sans_serif_font_family = 'DejaVu LGC Sans'
        settings.props.serif_font_family = 'DejaVu LGC Serif'
        settings.props.monospace_font_family = 'DejaVu LGC Sans Mono'
        settings.props.enforce_96_dpi = True
        settings.props.auto_shrink_images = False #FIXME: This does not seem to work
        settings.props.enable_plugins = False
        settings.props.enable_scripts = False
        settings.props.default_font_size = 12
        settings.props.default_monospace_font_size = 10
        
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_NEVER)
        self._dpi = 96
        sw.set_size_request(_mm_to_pixel(PAGE_WIDTH, self._dpi), _mm_to_pixel(PAGE_HEIGHT, self._dpi))
        sw.add(self._temp_view)
        self._temp_win.add(sw)
        self._temp_view.connect('load-finished', self._page_load_finished_cb)
           
        self._temp_win.show_all()
        self._temp_win.unrealize()
        
        self._temp_view.open(self._filelist[self._count])
       
    def _page_load_finished_cb(self, v, frame):
        f = v.get_main_frame()
        pageheight = f.get_height()
                
        if pageheight <= _mm_to_pixel(PAGE_HEIGHT, self._dpi):
            pages = 1
        else:
            pages = pageheight/float(_mm_to_pixel(PAGE_HEIGHT, self._dpi))
        for i in range(1, int(math.ceil(pages) + 1)):
            if pages - i < 0:
                pagelen = (pages - math.floor(pages))/pages
            else:
                pagelen = 1/pages
            self._pagemap[float(self._pagecount + i)] = (f.props.uri, (i-1)/pages, pagelen)
        
        self._pagecount += math.ceil(pages)
        self._filedict[f.props.uri.replace('file://', '')] = math.ceil(pages)
        self._bookheight += pageheight
        
        if self._count+1 >= len(self._filelist):
            self._temp_win.destroy()
            self.emit('paginated')
        else:
            self._count += 1
            self._temp_view.open(self._filelist[self._count])
            
            
    def get_file_for_pageno(self, pageno):
        return self._pagemap[pageno][0]
    
    def get_scrollfactor_pos_for_pageno(self, pageno):
        return self._pagemap[pageno][1]

    def get_scrollfactor_len_for_pageno(self, pageno):
        return self._pagemap[pageno][2]
    
    def get_pagecount_for_file(self, file):
        return self._filedict[file]
    
    def get_total_pagecount(self):
        return self._pagecount

    def get_total_height(self):
        return self._bookheight


class _JobFind(gobject.GObject):
    __gsignals__ = {
        'updated': (gobject.SIGNAL_RUN_FIRST,
                          gobject.TYPE_NONE,
                          ([]))
    }
    def __init__(self, document, start_page, n_pages, text, case_sensitive=False):
        gobject.GObject.__init__(self)
        
        self._document = document
        self._start_page = start_page
        self._n_pages = n_pages
        self._text = text
        self._case_sensitive = case_sensitive
        self.flattoc = self._document.get_flattoc()
        self._matchfilelist = []
        self._current_file_index = 0
        
        #self.emit('updated')
        gobject.idle_add(self._start_search)
        
    def get_next_file(self):
        self._current_file_index += 1
        try:
            path = self._matchfilelist[self._current_file_index]
        except IndexError:
            self._current_file_index = 0
            path = self._matchfilelist[self._current_file_index]
   
        return path

    def get_prev_file(self):
        self._current_file_index -= 1
        try:
            path = self._matchfilelist[self._current_file_index]
        except IndexError:
            self._current_file_index = -1
            path = self._matchfilelist[self._current_file_index]
   
        return path
    
    def _start_search(self):
        for entry in self.flattoc:
            name, file = entry
            filepath = os.path.join(self._document.get_basedir(), file)
            f = open(filepath)
            if self._searchfile(f):
                self._matchfilelist.append(file)
            f.close()
        
        self.emit('updated')
        
        return False
    
    def _searchfile(self, fileobj):
        soup = BeautifulSoup.BeautifulSoup(fileobj)
        body = soup.find('body')
        tags = body.findChildren(True)
        for tag in tags:
            if not tag.string is None: 
                if tag.string.find(self._text) > -1:
                    return True
    
        return False
    
    def get_search_text(self):
        return self._text
    
    def get_case_sensitive(self):
        return self._case_sensitive