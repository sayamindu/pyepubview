import os
from lxml import etree


class EpubInfo(): #TODO: Cover the entire DC range
    def __init__(self, file):
        self._tree = etree.parse(file)
        self._root = self._tree.getroot()
        self._e_metadata = self._root.find('{http://www.idpf.org/2007/opf}metadata')
        
        self.title = self._get_title()
        self.creator = self._get_creator()
        self.date = self._get_date()
        self.subject = self._get_subject()
        self.source = self._get_source()
        self.rights = self._get_rights()
        self.identifier = self._get_identifier()
        self.language = self._get_language()
        
    
    def _get_data(self, tagname):
        element = self._e_metadata.find(tagname)
        return element.text
    
    def _get_title(self):
        return self._get_data('{http://purl.org/dc/elements/1.1/}title')
        
    def _get_creator(self):
        return self._get_data('{http://purl.org/dc/elements/1.1/}creator')
        
    def _get_date(self):
        #TODO: iter
        return self._get_data('{http://purl.org/dc/elements/1.1/}date')

    def _get_source(self):
        return self._get_data('{http://purl.org/dc/elements/1.1/}source')

    def _get_rights(self):
        return self._get_data('{http://purl.org/dc/elements/1.1/}rights')

    def _get_identifier(self):
        #TODO: iter
        element = self._e_metadata.find('{http://purl.org/dc/elements/1.1/}identifier')
        return {'id':element.get('id'), 'value':element.text}

    def _get_language(self):
        return self._get_data('{http://purl.org/dc/elements/1.1/}language')

    def _get_subject(self):
        subjectlist = []
        for element in self._e_metadata.iterfind('{http://purl.org/dc/elements/1.1/}subject'):
            subjectlist.append(element.text)
            
        return subjectlist
        