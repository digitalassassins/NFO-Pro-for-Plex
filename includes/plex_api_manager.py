from PyQt6.QtCore import QObject, QThread, pyqtSignal
import requests
import json
import os
from plexapi.base import Playable
from plexapi.exceptions import NotFound, Unauthorized
from plexapi.media import Image, Theme
from plexapi.server import PlexServer
from plexapi.video import Episode, Show, Season, Movie
from plexapi.utils import toJson
from requests import RequestException
from includes.file_manager import PlexNFOFileManager

class PlexNFOPlexAPIManager(QObject):
    
    def __init__(self, scan_logger=None):
        super().__init__()
        self.plexServerConnected = False
        self.fileManager = PlexNFOFileManager()
        self.local_folders_split = {}
        self.thread = {}
        self.scan_logger = scan_logger
    
    def connect(self, plex_url, plex_token):
        if self.plexServerConnected == False:
            self.plex_url = plex_url
            self.plex_token = plex_token
            self.serverConnection = PlexServer(self.plex_url, self.plex_token, timeout=120)
            self.plexServerConnected = True
    
    def logger(self, text, status=None):
        ''' logger that only triggers if the scan logger has been send '''
        if self.scan_logger:
            self.scan_logger(text, status)
    
    def get_local_folders_split(self):
        if not self.local_folders_split:
            settings = self.fileManager.load_settings()
            for folder_type in settings["folders"]:
                if not self.local_folders_split.get(folder_type, False):
                    self.local_folders_split[folder_type] = []
                for key in list(settings["folders"][folder_type]):
                    self.local_folders_split[folder_type].append({f'{ settings["folders"][folder_type][key]["path"] }': settings["folders"][folder_type][key]["psplit"] })
    
    def cross_reference_paths(self, key1, list1, key2, list2):
        if [item for item in list1 if item in list2]:
            #print("--- Found"+ key1 +" in "+ key2 + " ---")
            return key2 + ":||:" + key1
    
    def locations_match(self, ltype, svr_loc_list):
        from pathlib import Path
        matched_paths = []
        self.get_local_folders_split()
        ## we explode each server location list and match them against each exploded local list
        client_list = []
        if self.local_folders_split.get(ltype, False):
            for location in self.local_folders_split[ltype]:
                client_list.append( location )
        ## get the server list exploded
        server_list = []
        for location in svr_loc_list:
            parts = Path(location).parts
            server_list.append({ f"{location}": parts })
        
        #print("-----------------------------------")
        if not client_list or not server_list:
            print("No Folders to Match Against")
            return ## no list to match against
            
        #print("Server List: ", server_list)
        #print("Client List: ", client_list)
        
        for clist_items in client_list:
            for cpath, clist in clist_items.items():
                for slist_items in server_list:
                    for spath, slist in slist_items.items():
                        list_match = self.cross_reference_paths(cpath, clist, spath, slist)
                        if list_match:
                            matched_paths.append( list_match )
                            
        if matched_paths:
            return matched_paths
        #print("-----------------------------------")
    
    def get_images(self, video):
        ## Images
        image_data = []
        for image in video.images:
            image_data.append({"type": image.type, "url": image.url, "web_url": video.url(image.url) })
        return {"images": image_data}
    
    def get_season_images(self, video, show_art):
        ## Images
        image_data = []
        existing_list = []
        for simage in show_art:
            existing_list.append(simage.url)        
        for image in video.images:
            if image.url not in existing_list:
                image_data.append({"type": image.type, "url": image.url, "web_url": video.url(image.url) })
        return {"images": image_data}
    
    def get_media(self, video):
        media_data = []
        for media in video.media:
            media_data.append( json.loads(toJson(media)) )
        return {"media": media_data}
    
    def get_labels(self, video):
        label_data = []
        for label in video.labels:
            label_data.append( label.tag )
        return {"labels": label_data}
        
    def get_actors(self, video):
        ## Actors
        actor_data = []
        for order, actor in enumerate(video.roles):
            actor_data.append( {"name":actor.tag, "role": actor.role, "order": str(order), "thumb": actor.thumb} )
        return {"actors": actor_data}
    
    def get_additional(self, video):
        for part in video.iterParts():
            part_data = json.loads(toJson(part)) 
        return part_data
    
    def get_guids(self, video):
        guids_data = []
        for guid in video.guids:
            id_type, sep, id_value = guid.id.partition("://")
            guids_data.append({"type": id_type, "value": id_value})
        return {"guids": guids_data}
    
    def get_ratings(self, video):
        ## Ratings:
        rating_data = []
        for rating in video.ratings:
            if rating.type != "audience":
                continue
            rate_site, __, __ = rating.image.partition("://")
            rating_data.append({"site": rate_site, "rating": rating.value})
        return {"ratings": rating_data}
    
    def get_countries(self, video):
        ## Countries
        country_data = []
        if json.loads(toJson(video)).get("countries", False):
            for country in video.countries:
                country_data.append(country.tag)
            return {"countries": country_data}
        else:
            return {}
    
    def get_writers(self, video):
        ## Writers
        writer_data = []
        if json.loads(toJson(video)).get("writers", False):
            for writer in video.writers:
                writer_data.append(writer.tag)
            return {"writers": writer_data}
        else:
            return {}
            
    def get_directors(self, video):
        ## Directors
        director_data = []
        if json.loads(toJson(video)).get("directors", False):
            for director in video.directors:
                director_data.append(director.tag)
            return {"directors": director_data}
        else:
            return {}
    
    def get_genres(self, video):
        ## Genres
        genre_data = []
        if json.loads(toJson(video)).get("genres", False):
            for genre in video.genres:
                genre_data.append(genre.tag)
            return {"genres": genre_data}
        else:
            return {}
    
    def get_collections(self, video):
        ## Collections
        collection_data = []
        if json.loads(toJson(video)).get("collections", False):
            for collection in video.collections:
                collection_data.append(collection.tag)
            return {"collections": collection_data}
        else:
            return {}
    
    def get_locations(self, video):
            location_data = []
            for location in video.locations:
                location_data.append(location)
                #return json.loads(toJson(location))
                return {"locations": location_data}
            return {}
    
    def get_seasons(self, video):
        season_data = {}
        for season in video.seasons():
            episode_data = {}
            season_data[season.index] = json.loads(toJson(season))
            season_data[season.index] = season_data[season.index] | self.get_guids(season) | self.get_ratings(season) | self.get_labels(season) | self.get_season_images(season, video.images)
            season_data[season.index]["episodes"] = {}
            for episode in season.episodes():
                episode_data[episode.index] = json.loads(toJson( episode ))
                episode_data[episode.index] = episode_data[episode.index] | self.get_labels(video) | self.get_season_images(episode, video.images) | self.get_media(episode) | self.get_locations(episode)
                episode_data[episode.index]["season_no"] = episode.seasonNumber
                episode_data[episode.index]["episode_no"] = episode.episodeNumber
                episode_data[episode.index]["season_episode"] = episode.seasonEpisode
                ## Append the episode data to the episode
                season_data[season.index]["episodes"] = season_data[season.index]["episodes"] | episode_data
        return season_data
    
    def find_item_by_guid(self, section, guid):
        ''' find an item in a library section by its agent guid '''
        ## try the server-side guid filter first (fast, one request)
        try:
            results = section.search(guid=guid)
            if results:
                return results[0]
        except Exception:
            pass  # filter not supported for this guid, fall through

        ## fall back to walking the library and comparing guids
        for item in section.all():
            if item.guid == guid:
                return item
        return None
    
    def fetch_single_item(self, library_id, guid):
        section = self.serverConnection.library.sectionByID(library_id)
        if guid and guid.startswith("plex"):
            video = section.getGuid(guid)
        else:
            video = self.find_item_by_guid(section, guid)
        if video is None:
            return None
        item_data = json.loads(toJson(video))
        
        if item_data:
            metadata = None ## set the metadata to none to prevent unbound error
            if item_data["type"] == "movie":                  
                metadata =  item_data | self.get_additional(video) | self.get_locations(video) | self.get_guids(video) | self.get_labels(video) | self.get_ratings(video) | self.get_media(video) | self.get_countries(video) | self.get_actors(video) | self.get_directors(video) | self.get_writers(video) | self.get_genres(video) | self.get_collections(video) | self.get_images(video)
                
            elif item_data["type"] == "show":
                item_data["seasons"] = self.get_seasons(video)
                metadata = item_data | self.get_actors(video) | self.get_directors(video) | self.get_guids(video) | self.get_labels(video) | self.get_ratings(video) | self.get_writers(video) | self.get_countries(video) | self.get_genres(video) | self.get_collections(video) | self.get_images(video)
        
            return metadata
        else:
            return None
    
    def fetch_library_items(self, library_id, item_callback=None):
        section = self.serverConnection.library.sectionByID(library_id)
        page_size = 50
        container_start = 0
        total = section.totalSize
        item_list = []

        while True:
            batch = section.search(container_start=container_start,
                                    maxresults=page_size)
            if not batch:
                break

            for video in batch:                
                item_data = json.loads(toJson(video))
                metadata = None ## set the metadata to none to prevent unbound error
                if item_data["type"] == "movie":                    
                    metadata =  item_data | self.get_additional(video) | self.get_locations(video) | self.get_guids(video) | self.get_labels(video) | self.get_ratings(video) | self.get_media(video) | self.get_countries(video) | self.get_actors(video) | self.get_directors(video) | self.get_writers(video) | self.get_genres(video) | self.get_collections(video) | self.get_images(video)
                    
                elif item_data["type"] == "show":
                    item_data["seasons"] = self.get_seasons(video)
                    metadata = item_data | self.get_actors(video) | self.get_directors(video) | self.get_guids(video) | self.get_labels(video) | self.get_ratings(video) | self.get_writers(video) | self.get_countries(video) | self.get_genres(video) | self.get_collections(video) | self.get_images(video)
                    
                if item_callback:
                    item_callback(metadata)

            container_start += len(batch)
            if container_start >= total:
                break
        
    def fetch_sections(self):
        p_sections = {}
        p_sections['movie'] = []
        p_sections['show'] = []
        ## get the sections from the server
        utsections = self.serverConnection.library.sections()
        for utsection in utsections:
            sectn_json = json.loads( toJson( utsection ) )
            location_list = json.loads( toJson( utsection.locations ) )
            total_items = {"total_items": json.loads( toJson(utsection.totalViewSize(sectn_json["type"]) ) ) }
            locations_json = {"locations": location_list }
            locations_match = self.locations_match(sectn_json["type"], location_list)
            self.logger("Found Library: " + sectn_json["title"])
            if locations_match:
                locations_match = {"location_match": locations_match}
                sectn = sectn_json | total_items | locations_json | locations_match | {"matched": True }
                self.logger(" Library <b>" + sectn_json["title"] + "</b> matches folder on local drive..", "success")
            else:
                sectn = sectn_json | total_items | locations_json | {"matched": False }
                self.logger("No matching folder for Library: <b>" + sectn_json["title"] + "</b> found on local drive..", "warning")
            
            #print(sectn)
            self.logger("Library: " + sectn_json["title"] + " added to Library Menu..")
            p_sections[ sectn["type"] ].append(sectn)
        
        self.local_folders_split = {} ## unset for the next scan incase options have changed
        return p_sections
        
    def download_media_url(self, save_path, web_url, save_filename: str, media_type="art", overwrite_file=False):
                
        headers = self.serverConnection._headers()        
        r = requests.get(url=web_url, headers=headers, stream=True)
        
        if r.status_code != 200:
            r = f"FAILED (HTTP code {r.status_code})"
            self.logger(r)
            print(r)
        else:
            content_type = r.headers.get("content-type", "")
            basetype, sep, ext = content_type.partition(";")[0].rpartition("/")
            
            if media_type == "logo":
                if not ext or ext == "jpeg":
                    ext = "png"
            elif media_type == "theme":
                if not ext or ext == "jpeg":
                    ext = "mp3"
            else:
                if not ext or ext == "jpeg":
                    ext = "jpg"
                    
            file_path = save_path +"/"+ f"{save_filename}.{ext}"
            try:
                if not os.path.isfile(file_path) or (os.path.isfile(file_path) and overwrite_file == True):
                    with open(file_path, "wb") as fd:
                        for chunk in r.iter_content(1024):
                            fd.write(chunk)
                else:
                    r = "SKIPPED"
                    self.logger(r)
                    print(r)
            except Exception as e:
                r = f"FAILED ({e})"
                self.logger(r)
                print(r)