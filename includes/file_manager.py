from PyQt6.QtGui import QPixmap, QImage

import os
import json
import errno
#import re, string
import sys
import shutil
from pathlib import Path

class PlexNFOFileManager():
    def __init__(self):
        self.home_dir() ## set the home directory for saving
        self.cache_dir() ## sets the cache directory
        
    def home_dir(self):
        self.home = os.path.join(Path.home(), '.plexNFOPro')
        if not Path(self.home).is_dir():
            Path(self.home).mkdir(parents=True, exist_ok=True)
    
    def cache_dir(self):
        self._cache = os.path.join(self.home, '.cache')
        if not Path(self._cache).is_dir():
            Path(self._cache).mkdir(parents=True, exist_ok=True)
    
    def library_dir(self, library):
        library_dir = os.path.join( self._cache, str(library) )
        library_image_dir = os.path.join( library_dir, "images" )
        library_data_dir = os.path.join( library_dir, "data" )
        if not Path(library_image_dir).is_dir():
            Path(library_image_dir).mkdir(parents=True, exist_ok=True)
        if not Path(library_data_dir).is_dir():
            Path(library_data_dir).mkdir(parents=True, exist_ok=True)
    
    def clear_library_cache(self):
        try:
            shutil.rmtree(self._cache)
            self.cache_dir()
        except OSError as e:
            print("Error: %s - %s." % (e.filename, e.strerror))
            
    def work_dir(self):
        return os.getcwd()
    
    def accepted_extensions(self, ext_type="All"):
        video_ext = ["mp4","avi","mkv","m2ts", "ts", "mov", "wmv", "mpegts", "3gpp", "flv", "mpeg", "wtv"]
        music_ext = ["m4a","mp3","aac","flac","alac", "mka", "aiff", "asf", "ogg", "wav"]
        image_ext = ["jpg","jpeg","png"] 
        text_ext = ["nfo","srt"]
        valid_extensions = []
        if ext_type == "All" or ext_type == "Video":
            valid_extensions.extend(video_ext)
        if ext_type == "All" or ext_type == "Audio":
            valid_extensions.extend(music_ext)
        if ext_type == "All" or ext_type == "Image":
            valid_extensions.extend(image_ext)
        if ext_type == "All" or ext_type == "Text":
            valid_extensions.extend(text_ext)
        return valid_extensions
    
    def valid_poster_names(self):
        return ["poster", "show", "folder", "cover", "default", "movie"]
    
    def valid_background_names(self):
        return ["art", "background", "backdrop", "fanart"]
    
    def valid_square_art_names(self):
        return ["square", "squareArt", "backgroundSquare"]
        
    def valid_banner_art_names(self):
        return ["banner"]
        
    def valid_season_poster_names(self):
        return ["season-specials-poster"]
    
    def valid_logo_names(self):
        return ["clearlogo", "logo"]
    
    def valid_art_filenames(self, art_type="All"):
        names = [] ## compile the names list
        if art_type == "All" or art_type == "Poster":
            names += self.valid_poster_names()
        if art_type == "All" or art_type == "Background":
            names += self.valid_background_names()
        if art_type == "All" or art_type == "Square":
            names += self.valid_square_art_names()
        if art_type == "All" or art_type == "Banner":
            names += self.valid_banner_art_names()
        if art_type == "All" or art_type == "Season":
            names += self.valid_season_poster_names()
        if art_type == "All" or art_type == "Logo":
            names += self.valid_logo_names()
            
        extensions = self.accepted_extensions("Image")
        valid_filenames = []
        for extension in extensions:
            for name in names:
                valid_filenames.append(name + "." + extension)
        return valid_filenames
    
    def valid_theme_names(self):
        return ["theme"]
    
    def valid_theme_filenames(self):
        return ["theme.mp3"]
    
    def check_valid_extension(self, filename, type_check):
        if type_check in ["Image", "Video", "Audio", "Text"]:
            if filename.endswith(tuple(self.accepted_extensions(type_check))):
                return True
            else:
                return False
    
    def remove_extension(self, file):
        filename, extension = os.path.splitext(file)
        return filename
    
    def get_extension(self, file):
        filename, extension = os.path.splitext(file)
        extension = str(extension).replace(".","").lower()
        return extension

    def recurse_all_files(self, scan_path, ext_list=[]):
        file_list=[]
        for root, dirs, files in os.walk(scan_path):
            for file in files:
                extension = self.get_extension(file)
                if extension in ext_list:
                    print("Extension:", extension)
                    print("Matches File:", file)
                    file_list.append(os.path.join(root, file))
    
    def list_folder_subfolders(self, folder):
        subfolders = [  f"{folder}/{f.name}" for f in os.scandir(folder) if f.is_dir() and not f.name.startswith(".") ]
        return subfolders
        
    def list_folder_files(self, folder):
        subfiles = [  f"{folder}/{f.name}" for f in os.scandir(folder) if f.is_file() and not f.name.startswith(".") ]
        return subfiles
        
    def fast_scandir(self, dirname):
        subfolders = [f.path for f in os.scandir(dirname) if f.is_dir() and not f.name.startswith(".") ]
        for dirname in list(subfolders):
            subfolders.extend(self.fast_scandir(dirname))
        return subfolders
    
    def load_image(self, fdir):
        ''' GUI-thread only: builds a QPixmap directly. '''
        img = os.path.join(fdir)
        pixmap = QPixmap(img)
        return pixmap
    
    def load_image_data(self, fdir):
        '''
        Thread-safe image loading for use off the GUI thread.
        QImage has no dependency on the GUI/paint engine, unlike
        QPixmap, so it's safe to construct from a worker thread.
        Convert the result to a QPixmap back on the GUI thread
        with QPixmap.fromImage().
        '''
        img = os.path.join(fdir)
        image = QImage(img)
        return image
    
    def mkdir_p(self, path):
        try:
            os.makedirs(path)
        except OSError as exc: 
            if exc.errno == errno.EEXIST and os.path.isdir(path):
                pass
            else: raise
        
    def safe_open_w(self, path):
        ''' Open "path" for writing, creating any parent directories as needed.'''
        self.mkdir_p(os.path.dirname(path))
        return open(path, 'w+', encoding='utf-8')
    
    def save_json_safe(self, file, save_data):
        sfile = os.path.join(self.home, file+'.json')
        with self.safe_open_w(sfile) as f:
            json.dump(save_data, f, ensure_ascii=False, indent=4)
    
    def save_json(self, file, save_data):
        sfile = os.path.join(self.home, file+'.json')
        with open(sfile, 'w+', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=4)
    
    def load_json(self, file):
        sfile = os.path.join(self.home, file+'.json')
        if Path(sfile).is_file():
            with open(sfile) as f:
                return json.load(f)
    
    def get_filename(self, fpath):
        ## returns only the name of the file
        return os.path.basename(fpath)
    
    def get_path(self, fpath):
        ## removes the filename and returns only the path of the name
        return os.path.dirname(fpath)
    
    def file_scan(self, folder, ftype=[], item_callback=None):
        files_list = []
        for root, dirs, files in os.walk(folder):
            for file in files:
                if file.endswith(tuple(ftype)):
                    if item_callback:
                        item_callback(os.path.join(root, file))
                    files_list.append(os.path.join(root, file))
        return files_list
    
    def list_files_in_library_data_dir(self, library_id, ext="", cut_ext=False):
        file_list = []
        directory = os.path.join(self._cache, str(library_id), "data")
        if os.path.isdir(directory):
            for file in os.listdir( directory ):
                if ext != "":
                    if file.endswith("."+ str(ext)):
                        if cut_ext:
                            file = file.replace("."+str(ext), "")
                        file_list.append(file)
                else:
                    if cut_ext:
                        file = file.replace("."+str(ext), "")
                    file_list.append(file)
                    
            return file_list
        else:
            return []
    
    def list_files_in_dir(self, directory, ext="", cut_ext=False):
        file_list = []
        directory = os.path.join(self.home, str(directory) )
        if os.path.isdir(directory):
            for file in os.listdir( directory ):
                if ext != "":
                    if file.endswith("."+ str(ext)):
                        if cut_ext:
                            file = file.replace("."+str(ext), "")
                        file_list.append(file)
                else:
                    if cut_ext:
                        file = file.replace("."+str(ext), "")
                    file_list.append(file)
                    
            return file_list
        else:
            return []
        
    
    def check_exists_in_list(self, check_list, match_list):
        return [ml for ml in match_list if any(cl in ml for cl in check_list)]
        
    def check_not_exists_in_list(self, check_list, match_list):
        return set(match_list) - check_list
    
    def clear_item_image_cache(self, library_id, slug):
        if library_id:
            image_types = ["background", "logo", "poster"]
            images = []
            cache_files = self.list_files_in_dir( os.path.join(self._cache, str(library_id), "images") )
            for itype in image_types:
                images.append(str(itype)+"_thumb_"+str(slug))
            matches = self.check_exists_in_list(images, cache_files)
            for match in matches:
                match_path = os.path.join(self._cache, str(library_id), "images", match)
                if Path(match_path).is_file():
                    try:
                        Path.unlink(match_path)
                        print("Removed Cache File:", match_path)
                    except OSError as e:
                        print("Error: %s - %s." % (e.filename, e.strerror))
    
    def load_settings(self):
        return self.load_json('settings')
    
    def load_saved_sections(self):
        return self.load_json('sections')
    
    def save_video_data(self, library_key, file_name, save_data):
        self.save_json_safe(os.path.join(self._cache, library_key, "data", file_name), save_data)
    
    def save_sections(self, save_data):
        self.save_json('sections', save_data)
    
    def save_settings(self, save_data):
        self.save_json('settings', save_data)
    
    def load_library_directory_json(self, library_id, jfile):
        jfile = os.path.join(self._cache, str(library_id), "data", jfile)
        if not Path(jfile).is_file():
            return None 
        else:
            with open(jfile, encoding="utf-8") as f:
                d = json.load(f)
                return d
    
    def load_home_directory_json(self, jfile):
        jfile = os.path.join(self.home, jfile)        
        if not Path(jfile).is_file():
            with open(jfile, 'w+', encoding='utf-8') as f:
                blank_obj = {}
                json.dump(blank_obj, f, ensure_ascii=False, indent=4)        
        with open(jfile, encoding="utf-8") as f:
            d = json.load(f)
            return d