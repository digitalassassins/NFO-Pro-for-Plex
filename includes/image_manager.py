from PIL import Image
from PyQt6.QtCore import QObject, pyqtSignal, QRunnable, QThreadPool, QTimer
# from multiprocessing import Pool
import os
from pathlib import Path
from includes.file_manager import PlexNFOFileManager
import json

class ImageTaskSignals(QObject):
    imageReady = pyqtSignal(int, object, str, int)

class ThumbnailTaskSignals(QObject):
    thumbnailReady = pyqtSignal(str, str, str, int)

class ThumbnailProcessTask(QRunnable):
    '''
    One unit of work (one image) that runs on a QThreadPool worker thread.
    Moves the actual PIL/disk work off the single persistent image_thread
    so multiple images can be processed concurrently.
    '''
    def __init__(self, imageManager, fileManager, cache_library_path, item):
        super().__init__()
        self.imageManager = imageManager
        self.fileManager = fileManager
        self.cache_library_path = cache_library_path
        self.item = item
        self.thumb_signals = ThumbnailTaskSignals()
    
    def run(self):
        item = self.item
        title = item.get("title")
        image_location = item.get("image")
        image_type = item.get("image_type")
        image_slug = item.get("image_slug")
        uuid = item.get("id")
        
        ## if the image is in the list of cached images just send back a cached image
        cache_filename = str(image_type) + "_thumb_" + str(image_slug) + "." + self.fileManager.get_extension(self.fileManager.get_filename(image_location))
        cache_filepath = os.path.join(self.cache_library_path, cache_filename)
        
        ## if the image is in the list of cached images just send back a cached image
        cache_filename = str(image_type) + "_thumb_" + str(image_slug) + "." + self.fileManager.get_extension(self.fileManager.get_filename(image_location))
        cache_filepath = os.path.join(self.cache_library_path, cache_filename)
        
        #print("Starting Thumbnail Generation:", image_location)
        
        if cache_filename not in self.imageManager.library_cache_files:
            created = self.imageManager.create_thumbnail(image_type, image_location, cache_filepath)
            if created:
                #print("Thumbnail Created:", item)
                image_location = cache_filepath
        else:
            image_location = cache_filepath
        
        self.thumb_signals.thumbnailReady.emit(title, image_location, image_type, uuid)
        
class ImageProcessTask(QRunnable):
    '''
    One unit of work (one image) that runs on a QThreadPool worker thread.
    Moves the actual PIL/disk work off the single persistent image_thread
    so multiple images can be processed concurrently.
    '''
    def __init__(self, imageManager, fileManager, cache_library_path, item):
        super().__init__()
        self.imageManager = imageManager
        self.fileManager = fileManager
        self.cache_library_path = cache_library_path
        self.item = item
        self.img_signals = ImageTaskSignals()

    def run(self):
        item = self.item
        wid = item.get("wid")
        image_location = item.get("image")
        image_type = item.get("image_type")
        image_slug = item.get("image_slug")
        gen_id = item.get("gen")
        
        ## if the image is in the list of cached images just send back a cached image
        cache_filename = str(image_type) + "_thumb_" + str(image_slug) + "." + self.fileManager.get_extension(self.fileManager.get_filename(image_location))
        cache_filepath = os.path.join(self.cache_library_path, cache_filename)

        if cache_filename not in self.imageManager.library_cache_files:
            created = self.imageManager.create_thumbnail(image_type, image_location, cache_filepath)
            if created:
                image_location = cache_filepath
        else:
            image_location = cache_filepath

        if image_type == "background":
            image_rtn = image_location
        if image_type == "poster":
            image_rtn = self.fileManager.load_image_data(image_location)
        if image_type == "logo":
            image_rtn = self.fileManager.load_image_data(image_location)
        if image_type == "episode":
            image_rtn = self.fileManager.load_image_data(image_location)

        self.img_signals.imageReady.emit(wid, image_rtn, image_type, gen_id)

class ThumbnailGenerationWorker(QObject):
    finished = pyqtSignal()         # emit job finished
    progress = pyqtSignal(int)      # emit the progress
    thumbnailsReady = pyqtSignal(list)   # batched results: [(title, image, image_type, uuid)...]
    
    def __init__(self, pool_threads=6, flush_interval=250):
        super().__init__()
        self.fileManager = PlexNFOFileManager()
        self.imageManager = PlexNFOImageManager(self.fileManager)        
        self.pool = QThreadPool()
        self.pool.setMaxThreadCount(pool_threads)   # 6 so its not bad on HDD but also fast on SSD
        self._pending_results = []
        self._flush_timer = QTimer(self)   # parented to self, so moveToThread carries it to image_thread too
        self._flush_timer.setInterval(flush_interval)  # send whatever's finished at most every 50ms
        self._flush_timer.timeout.connect(self._flush_results) #'# flush the results at the end of the timer to prevent flooding the GUI
    
    def switch_library(self, library_id):
        self.library_id = library_id
        self.imageManager.switch_library(self.library_id)
        self.cache_library_path = os.path.join(self.imageManager._cache, str(self.library_id), "images")
        self.fileManager.library_dir(self.library_id) ## check to see if the library directories exists, if not create them
    
    def _on_task_finished(self, title, image, image_type, uuid):
        ''' Runs on image_thread (queued here from whichever pool thread finished). Just buffer it - no GUI work. '''
        self._pending_results.append((title, image, image_type, uuid))

    def _flush_results(self):
        ''' Runs on image_thread every (X)ms. Sends everything that's finished since the last flush as one batch. '''
        if not self._pending_results:
            return
        batch = self._pending_results
        self._pending_results = []
        self.thumbnailsReady.emit(batch)
    
    def process_thumbnails(self, image_list):
        '''
        Slot connected to PlexNFOScanner.generateThumbnailsRequested. Each image is a QRunnable submitted to a QThreadPool, so up to setMaxThreadCount() images are decoded/cached concurrently.
        '''  
        if not self._flush_timer.isActive():
            self._flush_timer.start()   # first call runs on image_thread, so the timer binds to the right thread
        for item in image_list:
            #print(f"-------------------- << Queuing Image: {item['image_slug']} >> --------------------------")
            task = ThumbnailProcessTask(self.imageManager, self.fileManager, self.cache_library_path, item)
            task.thumb_signals.thumbnailReady.connect(self._on_task_finished)
            self.pool.start(task) 

class ImageLoadWorker(QObject):
    finished = pyqtSignal()         # emit job finished
    progress = pyqtSignal(int)      # emit the progress
    imagesReady = pyqtSignal(list)   # batched results: [(wid, image, image_type), ...]
    
    def __init__(self, pool_threads=6, flush_interval=250):
        super().__init__()
        self.fileManager = PlexNFOFileManager()
        self.imageManager = PlexNFOImageManager(self.fileManager)
        self.pool = QThreadPool()
        self.pool.setMaxThreadCount(pool_threads)   # 6 so its not bad on HDD but also fast on SSD
        self._pending_results = []
        self._flush_timer = QTimer(self)   # parented to self, so moveToThread carries it to image_thread too
        self._flush_timer.setInterval(flush_interval)  # send whatever's finished at most every 50ms
        self._flush_timer.timeout.connect(self._flush_results) #'# flush the results at the end of the timer to prevent flooding the GUI
    
    def switch_library(self, library_id):
        self.library_id = library_id
        self.imageManager.switch_library(self.library_id)
        self.cache_library_path = os.path.join(self.imageManager._cache, str(self.library_id), "images")
        self.fileManager.library_dir(self.library_id) ## check to see if the library directories exists, if not create them
    
    def _on_task_finished(self, wid, image, image_type, gen_id):
        ''' Runs on image_thread (queued here from whichever pool thread finished). Just buffer it - no GUI work. '''
        self._pending_results.append((wid, image, image_type, gen_id))

    def _flush_results(self):
        ''' Runs on image_thread every (X)ms. Sends everything that's finished since the last flush as one batch. '''
        if not self._pending_results:
            return
        batch = self._pending_results
        self._pending_results = []
        self.imagesReady.emit(batch)
    
    def process_images(self, image_list):
        '''
        Slot connected to PlexNFOPro.loadImagesRequested. Each image is a QRunnable submitted to a QThreadPool, so up to setMaxThreadCount() images are decoded/cached concurrently.
        '''  
        if not self._flush_timer.isActive():
            self._flush_timer.start()   # first call runs on image_thread, so the timer binds to the right thread
        for item in image_list:
            #print(f"-------------------- << Queuing Image: {item['image_slug']} >> --------------------------")
            task = ImageProcessTask(self.imageManager, self.fileManager, self.cache_library_path, item)
            task.img_signals.imageReady.connect(self._on_task_finished)
            self.pool.start(task)    

class PlexNFOImageManager():
    def __init__(self, fileManager):
        self.fileManager = fileManager
        self._cache = self.fileManager._cache
    
    def generate_thumbnail(self, filename, size, extension):
        try:
            im = Image.open(filename)
            if extension == "jpg" or extension == "jpeg":
                if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
                    # Create a solid white background matching the original image's size
                    background = Image.new("RGB", im.size, (255, 255, 255))
                    # Paste the image using itself as the mask to keep transparency layout
                    background.paste(im, mask=im.split()[3] if im.mode == "RGBA" else im)
                    im = background
                else:
                    # Ensure it's in standard RGB mode for JPEG saving
                    im = im.convert("RGB")
                im.draft("RGB", size)
            im.thumbnail(size)
            return im
        except Exception as e:
            return e
    
    def get_library_cached_files(self, library_dir):
        self.library_cache_files = self.fileManager.list_files_in_dir(library_dir)
        #print("-------------------- << image_manager.PlexNFOImageManager().get_library_cached_files() >> --------------------------")
        #print("Cache: ", self.library_cache_files)
        #print("-------------------- << image_manager.PlexNFOImageManager().get_library_cached_files() >> --------------------------")
    
    def switch_library(self, library_id):
        self.library_id = library_id
        self.library_dir = os.path.join( self._cache, str(self.library_id), "images" )
        #print("Library Dir:", self.library_dir)
        self.get_library_cached_files(self.library_dir)
    
    def save_cache_image(self, im, extension, save_location, save_quality=80):
        try:
            if save_location:
                im.save(save_location, quality=save_quality)
                return True
            else:
                return "Error: Filename or Library Path not sent.."
        except Exception as e:
            return e
    
    def create_thumbnail(self, image_type, filename, save_location, save_quality=80):
        size = None ## set the size to none
        extension = str(filename).split('.')[-1].lower()
        if image_type == "poster":
            size = (100,150)
        if image_type == "background":
            size = (365,205)
        if image_type == "logo":
            size = (150,80)
        if image_type == "episode":
            size = (360,200)
        if size != None:
            created = self.save_cache_image( self.generate_thumbnail( filename, size, extension), extension, save_location,  save_quality)
            if created == True:
                #print("Saved at:", save_location)
                return True ## image has been created and saved
            else:
                return created ## there has been an error, return the try exception error
        else:
            return False, "No Size Sent"    ## Error no size sent