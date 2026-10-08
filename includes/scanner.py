from PyQt6 import QtWidgets, sip
from PyQt6.QtCore import QObject, QThread, pyqtSignal
from includes.plex_api_manager import PlexNFOPlexAPIManager
from plexapi.utils import toJson
import ui.scan as scannerUIDialog
from includes.image_manager import ThumbnailGenerationWorker
from includes.file_manager import PlexNFOFileManager
from includes.plex_api_manager import PlexNFOPlexAPIManager
from includes.nfo_manager import PlexNFOGenerator
from includes.progress_calculator import ProgressCalculator

import sys
import os
import time
import json
import requests
import logging

class Scanner(QObject):
    finished = pyqtSignal()             ## send back task complete
    scannerLog = pyqtSignal(str, str, str)           ## send back the log
    scannerProgress = pyqtSignal()              ## send back the progress
    scannerItemReady = pyqtSignal(int, list)    ## emit items ready data
    scannerGenerateThumbnailsRequested = pyqtSignal(list) # Emitting this hands a batch of images off to the persistent image worker thread to generate thumbnails.
    scannerSwitchCacheLibrary = pyqtSignal(int) # Emitting this changes the active cache library folder for the image worker to change cache library folder
    scannerUpdateThumbnailTotal = pyqtSignal(int) # Emitting this changes the total thumbnails to wait for in the Scanner Worker
    scannerThumbnailsReady = pyqtSignal(list)   # Emitting this sends back up the stack the thumbnails that are ready
    scannerItemRefreshReady = pyqtSignal(dict)  # Emitting this sends back that a single item has been completed
    
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.plexServer = None                                          ## set the plex server object as none
        self.fileManager = PlexNFOFileManager()                         ## create a new file manager instance
        self.nfoManager = PlexNFOGenerator()
        self.valid_extensions = self.fileManager.accepted_extensions()  ## get the accepted extensions
        
        self.plex_connected = False                                     ## set the default plex connected flag as false
        self.connect_to_plex_server()                                   ## connect the plex server on init
        self.local_files = {}
        self.local_files_scanned_at = {}                                # when each library's video files were last scanned
        self.local_folders = {}
        self.reset_thumbnail_count()                                    ## set the thumbnail count to 0
        
        self.valid_names = {}  ## set the valid name variations on first run to prevent recalculating each variation on each single file scan
        self.valid_names["Poster"] = self.fileManager.valid_art_filenames("Poster")
        self.valid_names["Background"] = self.fileManager.valid_art_filenames("Background")
        self.valid_names["Logo"] = self.fileManager.valid_art_filenames("Logo")
        self.valid_names["Square"] = self.fileManager.valid_art_filenames("Square")
        self.valid_names["Theme"] = self.fileManager.valid_theme_filenames()
        
        ## set up the image loader thread
        self.image_thread = QThread()
        self.image_worker = ThumbnailGenerationWorker()
        self.image_worker.moveToThread(self.image_thread)
        self.scannerGenerateThumbnailsRequested.connect(self.image_worker.process_thumbnails)
        self.scannerSwitchCacheLibrary.connect(self.image_worker.switch_library)
        self.image_worker.thumbnailsReady.connect(self.scannerThumbnailsReady)
        self.image_thread.start()
    
    
    def get_plex_credentials(self):
        self.plex_url, self.plex_token = plex_url, plex_token = self.settings.get_plex_credentials()
        
    
    def connect_to_plex_server(self):
        if self.plexServer == None:
            self.plexServer = PlexNFOPlexAPIManager(self.log)
        if not self.plex_connected:
            self.get_plex_credentials()
            if self.plex_url != "" and self.plex_token != "":
                self.plexServer.connect( self.plex_url, self.plex_token )
    
    def reconnect_to_plex_server(self):
        self.plex_connected = False                                     ## set the plex connected flag as false
        self.get_plex_credentials()                                     ## get the plex new saved plex credentials
        self.connect_to_plex_server()                                   ## connect the plex server on init
        
    def log(self, text="", status=None, ltype="line"):
        self.scannerLog.emit(text, status, ltype)
    
    def reset_thumbnail_count(self):
        self.totalThumbnails = 0                                        ## set the total thumbnails as none
        self.processedThumbnails = 0                                    ## set the total processed thumbnails as none
    
    def set_cache_clear(self, cache_clear=False):
        self.cache_clear = cache_clear ## clear cache bool
    
    def list_folder_matched_single_section_by_id(self, library_id, progress_callback=None):
        sections = self.fileManager.load_saved_sections()
        if sections:
            for key in list(sections):
                for section in sections[key]:
                    ## now check if it is matched
                    if section["key"] == library_id and section["matched"] == True:
                        ## store the matched local folders
                        self.local_folders[section["key"]] = section["location_match"]
                        self.local_files[section["key"]] = []
                        
                        expected = int(section.get("total_items") or 0)  # estimate of how many files we'll find
                        found = 0
                        last_percent = -1
                        
                        def on_file_found(path):
                            nonlocal found, last_percent
                            found += 1
                            if progress_callback and expected:
                                percent = min(99, int(found * 100 / expected))  # never hit 100 until the scan is done
                                if percent != last_percent:                     # only report when the number changes
                                    last_percent = percent
                                    progress_callback(percent)
                        
                        for local_folder in section["location_match"]:
                            local_folder = str(local_folder.split(":||:")[1])
                            self.local_files[section["key"]].extend(
                                self.fileManager.file_scan(local_folder, self.fileManager.accepted_extensions("Video"), item_callback=on_file_found)
                            )
                        self.local_files_scanned_at[section["key"]] = time.time()
        
    def list_folder_matched_sections(self):
        
        def file_scan_callback(ffolder):
            self.log("File Found: "+ ffolder)
        
        totalItems = 0
        key_list = []
        sections = self.fileManager.load_saved_sections()
        if sections:
            for key in list(sections):
                for section in sections[key]:
                    ## now check if it is matched
                    if section["matched"] == True:
                        ## store the matched local folders
                        self.log("Matching Local Folders: "+ section["title"])
                        self.local_folders[section["key"]] = section["location_match"]
                        self.local_files[section["key"]] = []
                        for local_folder in section["location_match"]:
                            local_folder = str(local_folder.split(":||:")[1])
                            self.log(f"Scanning {local_folder} for Files..")
                            self.local_files[section["key"]].extend(
                                self.fileManager.file_scan(local_folder, self.fileManager.accepted_extensions("Video"), item_callback=file_scan_callback)
                            )
                            self.log(f'Found { len(self.local_files[section["key"]]) } local Files..')
                            #print(self.local_files[section["key"]])
                        ## calculate the total size for all sections
                        totalItems += section["total_items"]
                        key_list.append(section["key"])
                        self.log("Section Local Folder Match: "+ section["title"])
        ## send back the keys for each section that has a folder match
        return key_list, totalItems ## return back the key list and the total items found
    
    def scan_library_sections(self):
        sections = self.plexServer.fetch_sections()
        self.fileManager.save_sections(sections)
        return self.list_folder_matched_sections()
    
    def thumbnail_generator(self, image_list):
        # Hand this batch to the one persistent image worker thread to generate thumbnails
        self.scannerGenerateThumbnailsRequested.emit(image_list)
    
    def get_existing_in_library(self, library_id):
        return self.fileManager.list_files_in_library_data_dir( library_id, "json", True) #ending True cuts extension
    
    def scan_single_item(self, library_id, guid, attempts=3, known_files=None):
        self.scannerSwitchCacheLibrary.emit(library_id) ## switch the cache library on the thumbnail worker
        #if library_id not in self.local_files:
        #    folder_list_timer = time.perf_counter()
        #    ## safety net only: the library load should already have done this
        #    print("[single] WARNING: no stored file list, scanning folders now")
        #    self.list_folder_matched_single_section_by_id(library_id)
        #    print("[single] fallback folder scan took %.1fs" % (time.perf_counter() - folder_list_timer))
        
        pf_timer = time.perf_counter()
        metadata=None
        for attempt in range(1, attempts + 1):
            try:
                metadata = self.plexServer.fetch_single_item(library_id, guid)
                break
            except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
                logging.getLogger("plexnfopro").warning("Plex request failed (attempt %d/%d) for %s: %s", attempt, attempts, guid, e)
                print(f"[single] Plex request failed (attempt {attempt}/{attempts}): {e}")
                if attempt < attempts:
                    time.sleep(2 * attempt)   # wait a little longer each time before retrying
        print("[single] plex fetch took %.1fs" % (time.perf_counter() - pf_timer))
        
        if metadata:
            save_timer = time.perf_counter()
            #print(metadata)
            result = self.save_scanned_item(library_id, metadata, known_files)
            print("[single] save + art lookup took %.1fs" % (time.perf_counter() - save_timer))
            return result
    
    def scan_section_items(self, library_id):
        self.scannerSwitchCacheLibrary.emit(library_id) ## switch the cache library on the thumbnail worker
        if self.cache_clear:
            exists_il = [] ## overwrites all existing entries in cache
            self.log("Clear Cache selected, completing a full Server scan..")
        else:
            exists_il = self.get_existing_in_library(library_id)
            self.log("Found "+ str(len(exists_il)) + " existing items in the library cache, processing will be skipped..")
        
        def process_item_callback(metadata):
            if metadata["slug"] not in exists_il:
                self.log("<b><i>New Item:</i></b> " + metadata["title"] + " found downloading data..")
                self.save_scanned_item(library_id, metadata)
            else:
                self.log(metadata["title"] + " already found in library, Skipping download..")
            self.scannerProgress.emit()
        
        self.plexServer.fetch_library_items(library_id, item_callback=process_item_callback)
    
    def check_for_local_file_to_retrieve_local_folder(self, vfile, librarySectionID, known_files=None):
        vfile = self.fileManager.get_filename(vfile)
        pool = known_files if known_files is not None else self.local_files[librarySectionID]
        match = [item for item in pool if str(vfile) in item]
        if match:
            return match[0]
        else:
            return None
    
    def clear_cache(self):
        self.fileManager.clear_library_cache()
    
    def get_server_images(self, images):
        img_meta = {}
        for image in images:
            image_type = image.get("type")
            if image_type == "coverPoster": img_meta["server_poster"] = True 
            if image_type == "background": img_meta["server_background"] = True 
            if image_type == "clearLogo": img_meta["server_logo"] = True 
            if image_type == "backgroundSquare": img_meta["server_square"] = True
            if image_type == "snapshot": img_meta["server_thumb"] = True
        return img_meta
        
    def check_for_tv_art_locations(self, metadata):
        
        ## workout the valid season posters
        scount = 0
        valid_season_posters = []
        while scount < metadata["seasonCount"]+1:
            scount += 1
            valid_season_posters.append("Season"+ str(scount) )
            valid_season_posters.append("Season"+ str(scount) +"-poster")
            if scount < 10:
                valid_season_posters.append("Season0"+ str(scount) )
                valid_season_posters.append("Season0"+ str(scount) +"-poster")

        ## create the empty lists for thumbnail items and root show season poster matches
        thumbnail_items = []
        season_posters_found = []
        
        for local_folder in metadata["local_folders"]:            
            folder_files = self.fileManager.list_folder_files(local_folder)
            folder_files = [self.fileManager.get_filename(item) for item in folder_files]            
            for file in folder_files:            
                if self.fileManager.check_valid_extension(file, "Image"):
                    ## poster
                    if any( name in file for name in self.valid_names["Poster"] ):
                        if file.lower().startswith("season") and file not in season_posters_found:
                            season_posters_found.append(file)
                        else:
                            metadata["local_poster"] = file
                            image_location = str( os.path.join(local_folder, metadata["local_poster"]) ).replace("\\","/")
                            thumbnail_items.append({ "title": metadata["title"], "image": image_location, "image_type":"poster", "image_slug": metadata['slug'], "gen": metadata['guid'].replace("plex://show/", "") })
                    ## background        
                    if any( name in file for name in self.valid_names["Background"] ):
                        metadata["local_background"] = file
                        image_location = str( os.path.join(local_folder, metadata["local_background"]) ).replace("\\","/")
                        thumbnail_items.append({ "title": metadata["title"], "image": image_location, "image_type":"background", "image_slug": metadata['slug'], "gen": metadata['guid'].replace("plex://show/", "") })
                    ## logo
                    if any( name in file for name in self.valid_names["Logo"] ):
                        metadata["local_logo"] = file
                        image_location = str( os.path.join(local_folder, metadata["local_logo"]) ).replace("\\","/")
                        thumbnail_items.append({ "title": metadata["title"], "image": image_location, "image_type":"logo", "image_slug": metadata['slug'], "gen": metadata['guid'].replace("plex://show/", "") })
                    ## square
                    if any( name in file for name in self.valid_names["Square"] ):
                        metadata["local_square"] = file
                elif file.endswith(".mp3"): # theme files are mp3
                    ## theme
                    if any( name in file for name in self.valid_names["Theme"] ):
                        metadata["local_theme"] = file                
                elif file.endswith(".nfo"): ## get if the file is an nfo extension
                    ## NFO file
                    metadata["local_nfo"] = file
        
        
        ## work out the season posters in main folder
        if len(season_posters_found) > 0:
            for file in season_posters_found:
                if any( name in file for name in valid_season_posters ):
                    season_no = int("".join([n for n in file if n.isdigit()]))
                    if metadata["seasons"].get(season_no):
                        metadata["seasons"][season_no]["local_poster"] = file
                        metadata["seasons"][season_no]["local_poster_folder"] = local_folder
                        image_location = str( os.path.join(local_folder, file) ).replace("\\","/")
                        thumbnail_items.append({ "title": str(metadata["title"]) + " Season " + str(season_no), "image": image_location, "image_type":"poster", "image_slug": str(metadata['slug']) + "-season-" + str(season_no), "gen": metadata['guid'].replace("plex://show/", "") })
                    else:
                        self.log("Could not detect local Season Metadata for " + metadata["title"] + " Season " + str(season_no) , "error")
        

        ## now run through each season folder and find any other artwork if the art is in the season folder
        for season_no, season in metadata["seasons"].items():
            episode_file_names = [self.fileManager.remove_extension(self.fileManager.get_filename(episode)) for episode in metadata["local_files"]]                
            if metadata["seasons"][season_no].get("local_folders"):
                for local_folder in metadata["seasons"][season_no]["local_folders"]:                        
                    folder_files = self.fileManager.list_folder_files(local_folder)
                    folder_files = [self.fileManager.get_filename(item) for item in folder_files]                        
                    for file in folder_files: 
                        if any( name in file for name in episode_file_names ):
                            for episode_no, episode in metadata["seasons"][season_no]["episodes"].items():
                                episode_filename = self.fileManager.remove_extension( self.fileManager.get_filename(metadata["seasons"][season_no]["episodes"][episode_no]["locations"][0]) )
                                if self.fileManager.check_valid_extension(file, "Image"):                                    
                                    if file.startswith(episode_filename) and file != metadata["seasons"][season_no]["episodes"][episode_no].get("local_thumb"):                                        
                                        metadata["seasons"][season_no]["episodes"][episode_no]["local_thumb"] = file
                                        ## Generates Thumbnails for large local episode snapshots
                                        image_location = str( os.path.join( self.fileManager.get_path(metadata["seasons"][season_no]["episodes"][episode_no]["locations"][0]), file) ).replace("\\","/")
                                        thumbnail_items.append({ "title": metadata["title"], "image": image_location, "image_type":"episode", "image_slug": metadata['slug']+"-ep-"+str(episode_no), "gen": metadata['guid'].replace("plex://show/", "") })
                                elif file.endswith(".nfo"): ## get if the file is a valid text extension
                                    if self.fileManager.remove_extension(file) in [self.fileManager.remove_extension( self.fileManager.get_filename(location) ) for location in episode["locations"] ]:
                                        metadata["seasons"][season_no]["episodes"][episode_no]["local_nfo"] = file
                                        metadata["seasons"][season_no]["episodes"][episode_no]["local_nfo_folder"] = local_folder
                        
                        # check for season backgrounds inside season folders
                        if any( name in file for name in self.valid_names["Background"] ):
                            metadata["seasons"][season_no]["local_background"] = file
                        
                        ## check for season posters inside season folder
                        if season_no < 10:
                            season_poster_search = "Season0"+ str(season_no)
                        else:
                            season_poster_search = "Season"+ str(season_no)
                        if season_poster_search in file:
                            metadata["seasons"][season_no]["local_poster"] = file
                            metadata["seasons"][season_no]["local_poster_folder"] = local_folder
                            
                        if file == "season.nfo":
                            ## NFO file
                            metadata["seasons"][season_no]["local_nfo"] = file
        
        ## set away the thumbnail generation for this batch of items
        self.totalThumbnails += int(len(thumbnail_items))
        self.scannerUpdateThumbnailTotal.emit(self.totalThumbnails)
        self.thumbnail_generator(thumbnail_items)
        
        return metadata
    
    def check_for_movie_art_locations(self, metadata):
        for local_folder in metadata["local_folders"]:
            folder_files = self.fileManager.file_scan( local_folder, self.fileManager.accepted_extensions("All") )
            folder_files = [self.fileManager.get_filename(item) for item in folder_files]
            thumbnail_items = []
            
            for file in folder_files:
                if self.fileManager.check_valid_extension(file, "Image"):
                    ## poster
                    if any( name in file for name in self.valid_names["Poster"] ):
                        if file.startswith("movieset-"): ## skip if it is a movie collection poster
                            pass
                        else:                            
                            metadata["local_poster"] = file
                            image_location = str( os.path.join(local_folder, metadata["local_poster"]) ).replace("\\","/")
                            thumbnail_items.append({ "title": metadata["title"], "image": image_location, "image_type":"poster", "image_slug": metadata['slug'], "gen": metadata['id'] })                
                    ## background        
                    if any( name in file for name in self.valid_names["Background"] ):
                        if file.startswith("movieset-"): ## skip if it is a movie collection background
                            pass
                        else: 
                            metadata["local_background"] = file
                            image_location = str( os.path.join(local_folder, metadata["local_background"]) ).replace("\\","/")
                            thumbnail_items.append({ "title": metadata["title"], "image": image_location, "image_type":"background", "image_slug": metadata['slug'], "gen": metadata['id'] })                
                    ## logo
                    if any( name in file for name in self.valid_names["Logo"] ):
                        metadata["local_logo"] = file
                        image_location = str( os.path.join(local_folder, metadata["local_logo"]) ).replace("\\","/")
                        thumbnail_items.append({ "title": metadata["title"], "image": image_location, "image_type":"logo", "image_slug": metadata['slug'], "gen": metadata['id'] })                
                    ## square
                    if any( name in file for name in self.valid_names["Square"] ):
                        metadata["local_square"] = file            
                elif file.endswith(".mp3"):
                    ## theme
                    if any( name in file for name in self.valid_names["Theme"] ):
                        metadata["local_theme"] = file
                
                elif file.endswith(".nfo"): ## get if the file is a valid text extension
                    ## NFO file
                    metadata["local_nfo"] = file
                
            ## set away the thumbnail generation for this batch of items
            self.totalThumbnails += int(len(thumbnail_items))
            self.scannerUpdateThumbnailTotal.emit(self.totalThumbnails)
            self.thumbnail_generator(thumbnail_items)
            
        return metadata
        
    def save_scanned_item(self, key, metadata, known_files=None):
        if metadata["type"] == "movie":                   
            file = metadata.get("file", False)
            
            if file:
                if not metadata.get("local_files"):
                    metadata["local_files"] = []
                if not metadata.get("local_folders"):
                    metadata["local_folders"] = []
                #print("metadataLID: ", metadata["librarySectionID"])
                match = self.check_for_local_file_to_retrieve_local_folder(file, metadata["librarySectionID"], known_files)
                if match:
                    ## server data
                    metadata = metadata | self.get_server_images(metadata["images"])
                    if metadata["theme"]: metadata["server_theme"] = True                        
                    ## local data
                    metadata["local_files"].append(match)                                       ## we have found a local file
                    metadata["local_folders"].append(self.fileManager.get_path(match))          ## get the folder path of the video file
                    metadata = self.check_for_movie_art_locations(metadata)                     ## find the art and nfo file locations identifying them using Plex standard file naming 
                    self.fileManager.save_video_data(str(key), str(metadata["slug"]), metadata) ## save the found data to a json file to the library key and use the video slug for filename
                    self.log("Local File Found, Saved Data: "+ metadata["title"], "success")
                else:
                    self.log("No Local File Found for: "+ metadata["title"], "warning")
            else:
                self.log("Plex has no file listing for: "+ metadata["title"], "error")
                
        elif metadata["type"] == "show":
            ## server data
            metadata = metadata | self.get_server_images(metadata["images"])
            if metadata["theme"]: metadata["server_theme"] = True
            
            ## run through each episode collecting each episode location as the library could be split between multiple locations
            episode_file_match = False
            for season_no, season in metadata["seasons"].items():                
                ## check the season images
                metadata["seasons"][season_no] = metadata["seasons"][season_no] | self.get_server_images(season["images"])
                for episode_no, episode in season["episodes"].items():
                    if episode.get("locations", False):
                        for location in episode["locations"]:
                            match = self.check_for_local_file_to_retrieve_local_folder(location, metadata["librarySectionID"], known_files)
                            if match:
                                ## we have found a local file, set the local files
                                if not metadata.get("local_files", False):
                                    metadata["local_files"] = []
                                if not metadata["seasons"][season_no].get("local_files", False):
                                    metadata["seasons"][season_no]["local_files"] = []
                                if not metadata["seasons"][season_no].get("local_folders", False):
                                    metadata["seasons"][season_no]["local_folders"] = []
                                if not metadata.get("local_folders", False):
                                    metadata["local_folders"] = []
                                ## now we append the local files
                                metadata["local_files"].append(match)
                                metadata["seasons"][season_no]["local_files"].append(match)                                
                                ## calculate the season folders
                                season_folder = self.fileManager.get_path(match)                                
                                if season_folder not in metadata["seasons"][season_no]["local_folders"]:
                                    metadata["seasons"][season_no]["local_folders"].append( season_folder )                                
                                ## work out the show folders
                                show_folder = self.fileManager.get_path(season_folder)
                                if show_folder not in metadata["local_folders"]:
                                    metadata["local_folders"].append( show_folder )                                
                                ## we have managed to match the episode file so we can save the data
                                episode_file_match = True
            if episode_file_match == True:
                ## now we check the art locations
                metadata = self.check_for_tv_art_locations(metadata)
                ## if any file has matched then we save the data
                self.fileManager.save_video_data(str(key), str(metadata["slug"]), metadata) ## save the found data to a json file to the library key and use the video slug for filename
        
        return metadata
        
    def generate_nfo_file(self, item, get_actors):        
        if item["type"] == "movie":
            self.nfoManager.generate_movie_nfo(item, get_actors)
        elif item["type"] == "show":
            self.nfoManager.generate_show_nfo(item, get_actors)
        return
    
    def generate_season_nfo_file(self, season, save_path):
        self.nfoManager.generate_season_nfo(season, save_path)
    
    def generate_episode_nfo_file(self, episode, save_path, save_filename, get_actors):
        self.nfoManager.generate_episode_nfo(episode, save_path, save_filename, get_actors)
    
    def download_media_file(self, save_path, web_url, save_filename, media_type="art"):
        self.plexServer.download_media_url(str(save_path), str(web_url), str(save_filename), str(media_type), True)
        return
    
    
class ScannerWorker(QObject):
    finished = pyqtSignal()             ## send back task complete
    scanLog = pyqtSignal(str)           ## send back the log
    progress = pyqtSignal(int)          ## send back the progress
    itemReady = pyqtSignal(int, list)   ## emit item ready data
    itemRefreshReady = pyqtSignal(int, dict) ## sent when we return a single item to refresh the GUI for a single widget
    #generateThumbnailsRequested = pyqtSignal(list) # Emitting this hands a batch of images off to the persistent image worker thread to generate thumbnails.
    
    def __init__(self, settings, scanner):
        super().__init__()
        self.settings = settings
        self.set_mode()                                                 ## set the default_mode to system scan
        self._scanner = scanner
        self.set_cache_clear()                                          ## set the default cache clear as False
        
        self.header_br = self.calc_br()
        self.totalItems = 0                                             ## set the default current items as none
        self.totalThumbnails = 0                                        ## set the total thumbnails as none
        self.processedThumbnails = 0                                    ## set the total processed thumbnails as none
        self.settings = settings                                        ## get the passed settings
        
        self._scanner.scannerProgress.connect(self.update_progress)
        self._scanner.scannerUpdateThumbnailTotal.connect(self.update_thumbnail_total)
        self._scanner.scannerLog.connect(self.log)
        self._scanner.scannerThumbnailsReady.connect(self.update_batch_thumbnails_in_log)
        
    def set_cache_clear(self, cache_clear=False):
        self.cache_clear = cache_clear                                  ## clear cache bool
        self._scanner.set_cache_clear(cache_clear)                      ## pass the cache clear to the worker
    
    def set_mode(self, mode="full", **kargs):
        self.mode = mode
        self.kargs = kargs
    
    def disconnect_scanner(self):
        for signal, slot in (
            (self._scanner.scannerProgress, self.update_progress),
            (self._scanner.scannerUpdateThumbnailTotal, self.update_thumbnail_total),
            (self._scanner.scannerLog, self.log),
            (self._scanner.scannerThumbnailsReady, self.update_batch_thumbnails_in_log),
        ):
            try:
                signal.disconnect(slot)
            except (TypeError, RuntimeError):
                pass   # already disconnected or already deleted
    
    def update_thumbnail_total(self, total):
        self.totalThumbnails = total
    
    def wait_for_thumbnails(self, stall_timeout=60):
        last_count = self.processedThumbnails
        last_change = time.perf_counter()
        while self.processedThumbnails < self.totalThumbnails:
            if self.processedThumbnails != last_count:
                last_count = self.processedThumbnails      # progress is being made, reset the stall clock
                last_change = time.perf_counter()
            elif time.perf_counter() - last_change > stall_timeout:
                msg = "Thumbnail generation stalled for (%d/%d), moving on" % (self.processedThumbnails, self.totalThumbnails)
                print("[thumbs]", msg)
                logging.getLogger("plexnfopro").warning(msg)
                break
            time.sleep(0.1)
    
    def log_thumbnail_progress(self):
        self.log("Currently Generating Thumbnail (" + str(self.processedThumbnails) + "/" + str(self.totalThumbnails) + ") ")
        percent = ProgressCalculator(self.totalThumbnails)
        self.progress.emit( int(percent.get_step_percent(self.processedThumbnails)) )
    
    def update_batch_thumbnails_in_log(self, items):
        for title, image, image_type, uuid  in items:
            self.processedThumbnails += 1
            #self.log( str(title) )
            self.log_thumbnail_progress() ## update the log with the current progress
            self.log( str(image_type).title() + " Thumbnail Generated for: " + str(title))
    
    def init_progress(self, total):
        self.percent = ProgressCalculator( int(total) )
        self.progress.emit( self.percent.add() )
    
    def update_progress(self, percent=None):
        if percent == None:
            self.progress.emit( self.percent.add() )
        else:
            self.progress.emit( percent )
    
    def clear_cache(self):
        if self.cache_clear:
            self.log("Clearing Cache Files:", None, "header")
            self._scanner.clear_cache()
            self.log(f"All Cache Files Removed...")
    
    def _labels(self, label):
        if label == "success":
            return '<span color="green"><b>SUCCESS:</b><span> '
        elif label == "warning":
            return '<span color="yellow"><b>WARNING:</b><span> '
        elif label == "error":
            return '<span color="red"><b>ERROR:</b><span> '
        elif label == "statistic":
            return '<span color="blue"><b>STAT:</b><span> '
        else:
            return ''
    
    def calc_head_spacer(self, title_len, line_len=60):
        si = 0
        hsize = int(line_len - title_len / 2)
        sp= " "
        spr=""
        while si < hsize:            
            spr = spr + sp
            si+=1
        return spr
            
    def calc_br(self, line_len=60):
        bi = 0
        br = "#"
        brr=""
        while bi < line_len:
            brr = brr + br
            bi += 1
        return brr
        
    def log_header(self, text="", status=None):
        title = str(self._labels(status)) + str(text)       
        spacer = self.calc_head_spacer(len(title))
        
        self.scanLog.emit("")
        self.scanLog.emit(f"{str(self.header_br)}")
        self.scanLog.emit(f"{str(self.header_br)}")
        self.scanLog.emit(f"{str(spacer + title + spacer)}")
        self.scanLog.emit(f"{str(self.header_br)}")
        self.scanLog.emit(f"{str(self.header_br)}")
        self.scanLog.emit("")
    
    def log_line(self, text="", status=None):
        self.scanLog.emit(str(self._labels(status)) + str(text))
        
    def log(self, text="", status=None, ltype="line"):
        if ltype == "header":
            self.log_header(text, status)
        else:
            self.log_line(text, status)
    
    def _run_mode(self):
        if self.mode == "full":
            ## run a clear cache if user checked
            self.clear_cache()
            
            ## first we scan the sections to get a list of libraries
            ## get list of libraries first
            self.log("Retrieving Plex Libraries...", None, "header")
            matched_libraries, self.totalItems = ( self._scanner.scan_library_sections() ) ## scans the server for sections returns a tuple that is split
            
            ## setup the percentage to track progress
            self.init_progress(self.totalItems)
            
            ## run through each matched library and get the items
            scan_wait_timer = time.perf_counter()
            self.log("Scanning Library Items...", None, "header")
            for library_id in matched_libraries:
                self._scanner.scan_section_items(library_id)
            print("[full] scan of library took %.1fs" % (time.perf_counter() - scan_wait_timer))
            self.log("Library Scan Time: %.1fs" % (time.perf_counter() - scan_wait_timer), "statistic")
            
            ## time the thumnail generation wait time
            thumb_wait_timer = time.perf_counter()
            self.wait_for_thumbnails()
            print("[full] thumbnail wait took %.1fs" % (time.perf_counter() - thumb_wait_timer))
            self.log("Thumbnail Generation Time: %.1fs" % (time.perf_counter() - thumb_wait_timer), "statistic")
            
            self._scanner.reset_thumbnail_count() ## reset the thumbnail counter
            self.log("Scan Complete", None, "header")
            
        elif self.mode == "single":
            item = self.kargs["item"]
            iwid = self.kargs["iwid"]
            library_id = item["librarySectionID"]
            guid = item["guid"]
            try:
                ## clear this item's cache ready for a refresh
                self._scanner.fileManager.clear_item_image_cache(item.get("librarySectionID"), item.get("slug"))
                ## now scan the single item
                scan_wait_timer = time.perf_counter()
                metadata = self._scanner.scan_single_item(library_id, guid, known_files=item.get("local_files"))
                print("[single] scan of single item took %.1fs" % (time.perf_counter() - scan_wait_timer))
                self.update_progress(50)
            
                ## time the thumnail generation wait time
                thumb_wait_timer = time.perf_counter()
                self.wait_for_thumbnails()
                print("[single] thumbnail wait took %.1fs" % (time.perf_counter() - thumb_wait_timer))
            
                if metadata:
                    self.itemRefreshReady.emit(iwid, metadata)
            except Exception:
                sys.excepthook(*sys.exc_info())   # shown by the global handler
            finally:
                self._scanner.reset_thumbnail_count() ## reset the thumbnail counter
        
        elif self.mode == "download":
            
            ## get the list of files to process
            item = self.kargs["item"]
            iwid = self.kargs["iwid"]
            settings = self.settings.store
            
            web_urls = {}
            for image in item["images"]:
                if image["type"] == "coverPoster":
                    web_urls["poster"] = image["web_url"]
                if image["type"] == "background":
                    web_urls["background"] = image["web_url"]  
                if image["type"] == "clearLogo":
                    web_urls["logo"] = image["web_url"]
                if image["type"] == "backgroundSquare":
                    web_urls["square"] = image["web_url"]
            
            ## run through each file and download each file
            local_nfo = item.get("local_nfo")
            if not local_nfo or ( local_nfo and settings.get("downloadNFO") == True and settings.get("overwriteNFO") ):
                self._scanner.generate_nfo_file(item, settings.get("saveActors", False)) ## Truthy to get the actors 
            
            if item.get("server_poster") == True and web_urls.get("poster"):                
                local_poster = item.get("local_poster", False)
                if local_poster:
                    no_local_poster_file = False
                else:
                    no_local_poster_file = True
                    local_poster = "poster"                    
                if no_local_poster_file or ( no_local_poster_file == False and settings.get("overwritePoster") == True ):
                    for local_folder in item["local_folders"]:
                        self._scanner.download_media_file(local_folder, web_urls["poster"], self._scanner.fileManager.remove_extension(local_poster))
            
            if item.get("server_background") == True and web_urls.get("background") and settings.get("downloadBackground") == True:
                local_bg = item.get("local_background")
                if local_bg:
                    no_local_bg_file = False
                else:
                    no_local_bg_file = True
                    local_bg = "background"
                if no_local_bg_file or ( no_local_bg_file == False and settings.get("overwriteBackground") == True ):
                    for local_folder in item["local_folders"]:
                        self._scanner.download_media_file(local_folder, web_urls["background"], self._scanner.fileManager.remove_extension(local_bg))
            
            if item.get("server_logo") == True and web_urls.get("logo") and settings.get("downloadLogo") == True:
                local_logo = item.get("local_logo")
                if local_logo:
                    no_local_logo_file = False
                else:
                    no_local_logo_file = True
                    local_logo = "logo"
                if no_local_logo_file or ( no_local_logo_file == False and settings.get("overwriteLogo") == True ):
                    for local_folder in item["local_folders"]:
                        self._scanner.download_media_file(local_folder, web_urls["logo"], self._scanner.fileManager.remove_extension(local_logo), "logo")
            
            if item.get("server_square") == True and web_urls.get("square") and settings.get("downloadSquare") == True:
                local_square = item.get("local_square")
                if local_square:
                    no_local_square_file = False
                else:
                    no_local_square_file = True
                    local_square = "square"
                    
                if no_local_square_file or ( no_local_square_file == False and settings.get("overwriteSquare") == True ):
                    for local_folder in item["local_folders"]:
                        self._scanner.download_media_file(local_folder, web_urls["square"], self._scanner.fileManager.remove_extension(local_square))
            
            if item.get("server_theme") == True and item.get("theme", False) != False and settings.get("downloadTheme") == True:
                
                if item.get("theme") != None and settings.get("plexURL") != None and settings.get("plexToken") != None:
                    theme_library_url = item.get("theme")
                    theme_web_url = str( settings.get("plexURL").rstrip('/') ) + str(theme_library_url) + "?X-Plex-Token=" + str( settings.get("plexToken") )
                    #print("Theme URL:", theme_web_url)
                    local_theme = item.get("local_theme")
                    if local_theme:
                        no_local_theme_file = False
                    else:
                        no_local_theme_file = True
                        local_theme = "theme"
                        
                    if no_local_theme_file or ( no_local_theme_file == False and settings.get("overwriteTheme") == True ):
                        for local_folder in item["local_folders"]:
                            self._scanner.download_media_file(local_folder, theme_web_url, self._scanner.fileManager.remove_extension(local_theme), "theme")
                else:
                    print("Couldnt find There Library URL: ", theme_library_url)
                    
            if item.get("type") == "show":
                
                for season_no, season in item["seasons"].items():
                    ## falsify the web url for season poster and background
                    this_season_poster_web_url = False
                    this_season_background_web_url = False
                    season_local_poster_folder = season.get("local_poster_folder", None)                        
                    
                    if settings.get("downloadSeasonNFO") == True:
                        if season.get("local_folders"):
                            for season_local_folder in season.get("local_folders"):
                                self._scanner.generate_season_nfo_file(season, season_local_folder) ## no actors in season info
                    
                    ## find the season web urls for artwork
                    for image in season["images"]:
                        if image["type"] == "coverPoster":
                            this_season_poster_web_url = image["web_url"]
                        if image["type"] == "background":
                            this_season_background_web_url = image["web_url"]
                    
                    if settings.get("downloadSeasonPoster") == True and this_season_poster_web_url != False:
                        ## download the season poster
                        local_season_poster = season.get("local_poster", False)
                        if local_season_poster:
                            no_local_season_poster_file = False
                        else:
                            no_local_season_poster_file = True
                            season_local_poster_folder = item.get('local_folders')[0]
                            if int(season_no) < 10:
                                local_season_poster = f"Season0{season_no}-poster"
                            else:
                                local_season_poster = f"Season{season_no}-poster"
                        if no_local_season_poster_file or ( no_local_season_poster_file == False and settings.get("overwriteSeasonPoster") == True ):
                                self._scanner.download_media_file(season_local_poster_folder, this_season_poster_web_url, self._scanner.fileManager.remove_extension(local_season_poster))
                    
                    if settings.get("downloadSeasonBackground") == True and this_season_background_web_url != False:
                        ## download the season background into the season folder
                        local_season_background = season.get("local_background", False)
                        if local_season_background:
                            no_local_season_background_file = False
                        else:
                            no_local_season_background_file = True
                        if no_local_season_background_file or ( no_local_season_background_file == False and settings.get("overwriteSeasonBackground") == True ):
                            for season_local_folder in season.get("local_folders"):
                                self._scanner.download_media_file(season_local_folder, this_season_background_web_url, self._scanner.fileManager.remove_extension("background"))
                                
                    ## now run through the episodes generating the nfo files
                    if settings.get("downloadEpisodeNFO") == True or settings.get("downloadEpisodeThumb") == True:
                        for episode_no, episode in season["episodes"].items():
                            if settings.get("downloadEpisodeNFO") == True:
                                local_ep_nfo = item.get("local_nfo", False)
                                local_ep_nfo_folder = item.get("local_nfo_folder", False)
                                if not local_ep_nfo:
                                    local_ep_nfo = self._scanner.fileManager.remove_extension(self._scanner.fileManager.get_filename(episode["locations"][0]) )
                                    local_ep_nfo_folder = season["local_folders"][0]
                                    self._scanner.generate_episode_nfo_file(episode, local_ep_nfo_folder, local_ep_nfo, settings.get("saveActors", False) )
                                elif local_ep_nfo and local_ep_nfo_folder and settings.get("overwriteEpisodeNFO"):
                                    self._scanner.generate_episode_nfo_file(episode, local_ep_nfo_folder, self._scanner.fileManager.remove_extension(local_ep_nfo), settings.get("saveActors", False) )
                            
                            ## if we have set to download thumbs, and the thumb exists on server then download
                            if settings.get("downloadEpisodeThumb") == True:
                                for image in episode.get("images"):
                                    if image.get("type") == "snapshot":                                    
                                        thumb_web_url = image.get("web_url")
                                        self._scanner.download_media_file(self._scanner.fileManager.get_path(episode.get("locations")[0]), thumb_web_url, self._scanner.fileManager.remove_extension(self._scanner.fileManager.get_filename( episode.get("locations")[0]) ), "thumb")
        
    def run(self):
        try:
            self._run_mode()
        except Exception:
            sys.excepthook(*sys.exc_info())   # reported by the global handler
        finally:
            self.update_progress(100)
            self.finished.emit()              # always runs, so the thread quits and _busy clears
        
class PlexNFOScanner(QObject):
    starting = pyqtSignal()             ## send back task starting
    finished = pyqtSignal()             ## send back task complete
    
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.init_scanner_ui()
        self._scanner = Scanner(self.settings)
        self._busy = False
    
    def reconnect_to_plex_server(self):
        print("Reconnecting to Plex..")
        self._scanner.reconnect_to_plex_server()
    
    def _clear_busy(self):
        self._busy = False
    
    def init_scanner_ui(self):
        self.scannerUI = scannerUIDialog.Ui_Scan()
        self.scannerDialog = QtWidgets.QDialog()
        self.scannerUI.setupUi(self.scannerDialog)
        self.scannerUI.scanButton.clicked.connect(self.start_scan)
    
    def clear_log_window(self):
        self.scannerUI.scanProgressTextLog.clear()
    
    def disable_buttons(self):
        self.scannerUI.scanButton.setEnabled(False)
        self.scannerUI.clearCacheCheckBox.setEnabled(False)
    
    def enable_buttons(self):
        self.scannerUI.scanButton.setEnabled(True)
        self.scannerUI.clearCacheCheckBox.setEnabled(True)
    
    def start_scan(self):
        if self._busy:
            self.log("Looks like you have already started a scan, please wait for the previous scan to finish before proceeding.")
            return False
            
        self._busy = True
        self.clear_log_window()
        self.thread = QThread()
        self.worker = ScannerWorker(self.settings, self._scanner)
        self.worker.set_cache_clear(self.scannerUI.clearCacheCheckBox.isChecked()) ## pass in if we should clear the cache on this scan
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.disable_buttons)
        self.thread.started.connect(self.worker.run)
        self.thread.started.connect(self.starting.emit)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.enable_buttons)
        self.thread.finished.connect(self._clear_busy)
        self.thread.finished.connect(self.finished.emit)
        self.worker.progress.connect(self.update_scan_progress)
        self.worker.scanLog.connect(self.log)
        self.thread.start()
    
    def single_item_scan(self, iwid, item, update_widget_callback=None, single_item_progress_callback=None, finished_callback=None):
        if self._busy:
            return False
            
        self._busy = True
        self.thread = QThread()
        self.worker = ScannerWorker(self.settings, self._scanner)
        self.worker.set_mode("single", iwid=iwid, item=item)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.thread.started.connect(self.starting.emit)
        self.worker.itemRefreshReady.connect(update_widget_callback)
        self.worker.progress.connect(single_item_progress_callback)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.disconnect_scanner)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self._clear_busy)
        self.thread.finished.connect(self.finished.emit)
        if finished_callback:
            self.thread.finished.connect(finished_callback)
        self.thread.start()
        return True
    
    def start_download_item(self, iwid, item, finished_callback=None):
        if self._busy:
            self.log("Looks like you have already started a scan, please wait for the previous scan to finish before proceeding.")
            return False
            
        self._busy = True
        self.clear_log_window()
        self.thread = QThread()
        self.worker = ScannerWorker(self.settings, self._scanner)
        self.worker.set_mode("download", iwid=iwid, item=item)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.thread.started.connect(self.starting.emit)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.disconnect_scanner)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self._clear_busy)
        self.thread.finished.connect(self.finished.emit)
        self.worker.progress.connect(self.update_scan_progress)
        self.worker.scanLog.connect(self.log)
        if finished_callback:
            self.thread.finished.connect(finished_callback)
        self.thread.start()
        return True
    
    def start_library_section_scan(self):      
        return self._scanner.scan_library_sections()
    
    def update_scan_progress(self, percent):
        self.scannerUI.scanProgressBar.setValue(percent)
    
    def log(self, text):
        self.scannerUI.scanProgressTextLog.append(str(text))

    def _open(self):
        ## open the dialog window
        self.scannerDialog.exec()
        return