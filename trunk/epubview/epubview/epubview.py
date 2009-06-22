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

import gtk, gtk.gdk
import gobject
import webkit

import os.path
import math

from epub import _Epub
from jobs import _JobPaginator as _Paginator


LOADING_HTML = '''
<div style="width:100%;height:100%;text-align:center;padding-top:50%;">
    <h1>Loading...</h1>
</div>
'''

class _View(gtk.HBox):
    __gproperties__ = {
        'has-selection' : (gobject.TYPE_BOOLEAN, 'whether has selection',
                  'whether the widget has selection or not',
                  0, gobject.PARAM_READABLE), 
    'zoom' : (gobject.TYPE_FLOAT, 'the zoom level',
                  'the zoom level of the widget',
                  0.5, 4.0, 1.0, gobject.PARAM_READWRITE)
    }    
    __gsignals__ = {
        'page-changed': (gobject.SIGNAL_RUN_FIRST,
                          gobject.TYPE_NONE,
                          ([]))
    }    
    def __init__(self):
        gobject.threads_init()
        gtk.HBox.__init__(self)
        
        self.connect("destroy", self._destroy_cb)

        self._ready = False
        self._paginator = None
        self._loaded_page = -1
        #self._old_scrollval = -1
        self._loaded_filename = None
        self._pagecount = -1
        self.__going_fwd = True
        self.__going_back = False
        self.__page_changed = False
        self.has_selection = False
        self.zoom = 1.0
        self._epub = None
        self._findjob = None
        self.__in_search = False
        self.__search_fwd = True
        
        self._sw = gtk.ScrolledWindow()
        self._view = webkit.WebView()
        self._view.load_string(LOADING_HTML, 'text/html', 'utf-8', '/')
        settings = self._view.get_settings()
        settings.props.default_font_family = 'DejaVu LGC Serif'
        settings.props.enable_plugins = False
        settings.props.enable_scripts = False
        self._view.connect('load-finished', self._view_load_finished_cb)
        self._view.connect('scroll-event', self._view_scroll_event_cb)
        self._view.connect('key-press-event', self._view_keypress_event_cb)
        self._view.connect('button-release-event', self._view_buttonrelease_event_cb)
        self._view.connect('selection-changed', self._view_selection_changed_cb)
        self._view.connect_after('populate-popup', self._view_populate_popup_cb)
        
        self._sw.add(self._view)
        self._sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_NEVER)
        self._v_vscrollbar = self._sw.get_vscrollbar()
        self._v_scrollbar_value_changed_cb_id = self._v_vscrollbar.connect('value-changed', \
                                                                        self._v_scrollbar_value_changed_cb)
        self._scrollbar = gtk.VScrollbar()
        self._scrollbar.set_update_policy(gtk.UPDATE_DISCONTINUOUS)
        self._scrollbar_change_value_cb_id = self._scrollbar.connect('change-value', \
                                                                      self._scrollbar_change_value_cb)
        self.pack_start(self._sw, expand = True, fill = True)
        self.pack_start(self._scrollbar, expand = False, fill = False)
        
        self._view.set_flags(gtk.CAN_DEFAULT|gtk.CAN_FOCUS)        
        
    def set_document(self, epubdocumentinstance):
        self._epub = epubdocumentinstance
        gobject.idle_add(self._paginate)

    def do_get_property(self, property):
        if property.name == 'has-selection':
            return self.has_selection
        elif property.name == 'zoom':
            return self.zoom
        else:
            raise AttributeError, 'unknown property %s' % property.name

    def do_set_property(self, property, value):
        if property.name == 'zoom':
            self.__set_zoom(value)
        else:
            raise AttributeError, 'unknown property %s' % property.name
    
    def get_has_selection(self):
        return self.get_property('has-selection')
    
    def get_zoom(self):
        return self.get_property('zoom')
    
    def set_zoom(self, value):
        self.set_property('zoom', value)
    
    def zoom_in(self):
        if self.can_zoom_in():
            self.set_zoom(self.get_zoom() + 0.1)
            return True
        else:
            return False

    def zoom_out(self):
        if self.can_zoom_out():
            self.set_zoom(self.get_zoom() - 0.1)
            return True
        else:
            return False
    
    def can_zoom_in(self):
        if self.zoom < 4:
            return True
        else:
            return False

    def can_zoom_out(self):
        if self.zoom > 0.5:
            return True
        else:
            return False
    
    def get_current_page(self):
        return self._loaded_page
    
    def get_current_file(self):
        #return self._loaded_filename
        if self._paginator: 
            return self._paginator.get_file_for_pageno(self._loaded_page)
        else:
            return None
    
    def get_pagecount(self):
        return self._pagecount
    
    def set_current_page(self, n):
        if n < 1 or n > self._pagecount:
            return False
        self._load_page(n)
        return True
        
    def next_page(self):
        if self._loaded_page == self._pagecount:
            return False
        self._load_next_page()
        return True
        
    def previous_page(self):
        if self._loaded_page == 1:
            return False
        self._load_prev_page()
        return True
    
    def copy(self):
        self._view.copy_clipboard()
    
    def find_next(self):
        self._view.grab_focus()
        self._view.grab_default()

        if self._view.search_text(self._findjob.get_search_text(), \
                               self._findjob.get_case_sensitive(), True, False):
            return
        else:
            path = os.path.join(self._epub.get_basedir(), self._findjob.get_next_file())
            self.__in_search = True
            self.__search_fwd = True
            self._load_file(path)
    
    def find_previous(self):
        self._view.grab_focus()
        self._view.grab_default()

        if self._view.search_text(self._findjob.get_search_text(), \
                               self._findjob.get_case_sensitive(), False, False):
            return
        else:
            path = os.path.join(self._epub.get_basedir(), self._findjob.get_prev_file())
            self.__in_search = True
            self.__search_fwd = False
            self._load_file(path)
            
    def _find_changed(self, job):
        self._view.grab_focus()
        self._view.grab_default()
        self._findjob = job
        self._view.search_text(self._findjob.get_search_text(), \
                               self._findjob.get_case_sensitive(), True, False)
        
    def __set_zoom(self, value):
        self._view.set_zoom_level(value)
        self.zoom = value
    
    def __set_has_selection(self, value):
        if value != self.has_selection:
            self.has_selection = value
            self.notify('has-selection')
    
    def _view_populate_popup_cb(self, view, menu):
        menu.destroy() #HACK
        return
    
    def _view_selection_changed_cb(self, view):
        # FIXME: This does not seem to be implemented in 
        # webkitgtk yet
        print view.has_selection()
    
    def _view_buttonrelease_event_cb(self, view, event):
        # Ugly hack
        self.__set_has_selection(view.can_copy_clipboard() \
                                 | view.can_cut_clipboard())
    
    def _view_keypress_event_cb(self, view, event):
        name = gtk.gdk.keyval_name(event.keyval)
        if name == 'Page_Down' or name == 'Down': 
            self.__going_back = False
            self.__going_fwd = True
        elif name == 'Page_Up' or name == 'Up':
            self.__going_back = True
            self.__going_fwd = False
            
        self._do_page_transition()

    def _view_scroll_event_cb(self, view, event):
        if event.direction == gtk.gdk.SCROLL_DOWN:
            self.__going_back = False
            self.__going_fwd = True
        elif event.direction == gtk.gdk.SCROLL_UP:
            self.__going_back = True
            self.__going_fwd = False

        self._do_page_transition() 
        
    def _do_page_transition(self):
        if self.__going_fwd:
            if self._v_vscrollbar.get_value() >= \
                self._v_vscrollbar.props.adjustment.props.upper - \
                    self._v_vscrollbar.props.adjustment.props.page_size:
                self._load_next_file()
                return True
        elif self.__going_back:
            if self._v_vscrollbar.get_value() == self._v_vscrollbar.props.adjustment.props.lower:
                self._load_prev_file()
                return True
        
        return False
        
    def _view_load_finished_cb(self, v, frame):
        filename = self._view.props.uri
        
        if self._loaded_page < 1 or filename == None:
            return False
        
        self._loaded_filename = filename.replace('file://', '')
        
        if self.__in_search:
            self._view.search_text(self._findjob.get_search_text(), \
                               self._findjob.get_case_sensitive(), \
                               self.__search_fwd, False)
            self.__in_search = False
        else: 
            self._scroll_page()
        
        
    def _scroll_page(self):
        pageno = self._loaded_page
        
        v_upper = self._v_vscrollbar.props.adjustment.props.upper
        v_lower = self._v_vscrollbar.props.adjustment.props.lower
        
        scrollfactor = self._paginator.get_scrollfactor_pos_for_pageno(pageno)
        self._v_vscrollbar.set_value(v_upper * scrollfactor)
        #self._old_scrollval = v_upper * scrollfactor
        
    def _paginate(self):
        filelist = []
        for i in self._epub._navmap.get_flattoc():
            filelist.append(os.path.join(self._epub._tempdir, i[1]))
            
        self._paginator = _Paginator(filelist)
        self._paginator.connect('paginated', self._paginated_cb)
    
    def _load_next_page(self):
        self._load_page(self._loaded_page + 1)

    def _load_prev_page(self):
        self._load_page(self._loaded_page - 1)
    
    def _v_scrollbar_value_changed_cb(self, scrollbar):
        if self._loaded_page < 1:
            return
        scrollval = scrollbar.get_value()
        scroll_upper = self._v_vscrollbar.props.adjustment.props.upper

        if self.__going_fwd == True and not self._loaded_page == self._pagecount:
            scrollfactor = self._paginator.get_scrollfactor_pos_for_pageno(self._loaded_page + 1)
            if scrollval != 0 and scrollval >= scroll_upper * scrollfactor:
                self._on_page_changed(self._loaded_page + 1)
        else:
            scrollfactor = self._paginator.get_scrollfactor_pos_for_pageno(self._loaded_page)
            if scrollval != 0 and scrollval < scroll_upper * scrollfactor:
                self._on_page_changed(self._loaded_page - 1)
        
    def _on_page_changed(self, pageno):
        self.__page_changed = True
        self._loaded_page = pageno
        self._scrollbar.handler_block(self._scrollbar_change_value_cb_id)
        self._scrollbar.set_value(pageno)
        self._scrollbar.handler_unblock(self._scrollbar_change_value_cb_id)
        self.emit('page-changed')
        
    def _load_page(self, pageno):
        if pageno > self._pagecount or pageno < 1:
            #TODO: Cause an exception
            return

        self._on_page_changed(pageno)
        filename = self._paginator.get_file_for_pageno(pageno)
        if filename != self._loaded_filename:
            self._loaded_filename = filename
            self._view.open(filename)
        else:
            self._scroll_page()
    
    def _load_next_file(self):
        cur_file = self._paginator.get_file_for_pageno(self._loaded_page)
        pageno = self._loaded_page
        while pageno < self._paginator.get_total_pagecount():
            pageno += 1
            if self._paginator.get_file_for_pageno(pageno) != cur_file:
                break
        
        self._load_page(pageno)

    def _load_file(self, path):
        #TODO: This is a bit suboptimal - fix it
        for pageno in range(1, self.get_pagecount()):
            filepath = self._paginator.get_file_for_pageno(pageno)
            if filepath.endswith(path):
                self._load_page(pageno)
                break

    def _load_prev_file(self):
        cur_file = self._paginator.get_file_for_pageno(self._loaded_page)
        pageno = self._loaded_page
        while pageno > 1:
            pageno -= 1
            if self._paginator.get_file_for_pageno(pageno) != cur_file:
                break
            
        self._load_page(pageno)

    def _scrollbar_change_value_cb(self, range, scrolltype, value):
        if scrolltype == gtk.SCROLL_STEP_FORWARD:
            self.__going_fwd = True
            self.__going_back = False
            if not self._do_page_transition():
                self._view.move_cursor(gtk.MOVEMENT_DISPLAY_LINES, 1)
        elif scrolltype == gtk.SCROLL_STEP_BACKWARD:
            self.__going_fwd = False
            self.__going_back = True
            if not self._do_page_transition():
                self._view.move_cursor(gtk.MOVEMENT_DISPLAY_LINES, -1)                
        elif scrolltype == gtk.SCROLL_JUMP:
            if value > self._scrollbar.props.adjustment.props.upper:
                self._load_page(self._pagecount)
            else:
                self._load_page(round(value))
        else:
            #self._load_page(round(value))
            print 'Warning: unknown scrolltype %s with value %f' % (str(scrolltype), value)
        
        self._scrollbar.set_value(self._loaded_page) #FIXME: This should not be needed here
        
        if self.__page_changed == True:
            self.__page_changed = False
            return False
        else:
            return True
        
    def _paginated_cb(self, object):
        self._ready = True
        
        self._pagecount = self._paginator.get_total_pagecount()
        self._scrollbar.set_range(1.0, self._pagecount - 1.0)
        self._scrollbar.set_increments(1.0, 1.0)
        self._view.grab_focus()
        self._view.grab_default()
        if self._loaded_page < 1:
            self._load_page(1)
        
        

    def _destroy_cb(self, widget):
        self._epub.close()

