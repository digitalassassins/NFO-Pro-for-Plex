import os
from datetime import datetime, UTC
from xml.etree import ElementTree as xmlET

class PlexNFOGenerator():
    def __init__(self):
        self.init = True
        
    def generate_movie_nfo(self, movie, get_actors=True):
        
        """Create a NFO file content from a movie."""
        # display tags that are not taken into account
        root = xmlET.Element("movie")

        for country in movie.get("countries", []):
            xmlET.SubElement(root, "country").text = country
        
        if movie.get("addedAt"):
            new_zone = movie.get("addedAt").replace("T", " ").replace("Z", "")
            addedAt = datetime.strptime(new_zone, '%Y-%m-%d %H:%M:%S').replace(tzinfo=UTC)
            xmlET.SubElement(root, "dateadded").text = addedAt.strftime('%Y-%m-%d %H:%M:%S')
        
        if movie.get("lastViewedAt"):
            new_zone = movie.get("lastViewedAt").replace("T", " ").replace("Z", "")
            lastViewedAt = datetime.strptime(new_zone, '%Y-%m-%d %H:%M:%S').replace(tzinfo=UTC)
            xmlET.SubElement(root, "lastplayed").text = lastViewedAt.strftime('%Y-%m-%d %H:%M:%S')
        
        if movie.get("originalTitle"):
            xmlET.SubElement(root, "originalTitle").text = movie.get("originalTitle")
        
        if int(movie.get("viewCount") or 0) > 0 or movie.get("lastViewedAt"):
            xmlET.SubElement(root, "playcount").text = str(movie.get("viewCount"))
        
        if int(movie.get("viewCount")) > 0 or movie.get("lastViewedAt"):
            xmlET.SubElement(root, "watched").text = "true"
        
        if movie.get("summary"):
            xmlET.SubElement(root, "plot").text = movie.get("summary")
        
        if movie.get("originallyAvailableAt"):
            released = movie.get("originallyAvailableAt").split("T")[0]
            # validate it's a real date, keep as YYYY-MM-DD string
            released = datetime.strptime(released, '%Y-%m-%d').strftime('%Y-%m-%d')
            xmlET.SubElement(root, "releasedate").text = released
            xmlET.SubElement(root, "premiered").text = released
        
        if movie.get("duration"):
            xmlET.SubElement(root, "runtime").text = str( int(movie.get("duration")) // 60_000 )
        
        if movie.get("titleSort"):
            xmlET.SubElement(root, "sorttitle").text = movie.get("titleSort")
            
        if movie.get("studio"):
            xmlET.SubElement(root, "studio").text = movie.get("studio")
            
        if movie.get("tagline"):
            xmlET.SubElement(root, "tagline").text = movie.get("tagline")
            
        xmlET.SubElement(root, "title").text = movie.get("title", "")
        
        for guid in movie.get("guids", []):
            id_type = guid.get("type")
            id_value = guid.get("value")
            
            id_element = xmlET.SubElement(root, "uniqueid", type=id_type)
            id_element.text = id_value
            if id_type == "imdb":
                id_element.set("default", "true")
                xmlET.SubElement(root, "id").text = id_value
                xmlET.SubElement(root, "imdbid").text = id_value
            elif id_type == "tmdb":
                xmlET.SubElement(root, "tmdbid").text = id_value
            elif id_type == "tvdb":
                xmlET.SubElement(root, "tvdbid").text = id_value
            elif id_type == "mbid":
                xmlET.SubElement(root, "idmbid").text = id_value
        
        if movie.get("year"):
            xmlET.SubElement(root, "year").text = str( movie.get("year") )
            
        if movie.get("contentRating"):
            cRating = movie.get("contentRating").replace("fr/", "FR-").replace("-Unrated", "-U").replace("-TP", "-Tous publics")
            xmlET.SubElement(root, "mpaa").text = cRating
        
        ratings = movie.get("ratings", [])
        if len(ratings) > 0:
            site_ratings = xmlET.SubElement(root, "ratings")
            for row in ratings:
                site_rating = xmlET.SubElement(site_ratings, "rating", name=row.get("site"), max="10")
                if row.get("site") == "imdb":
                    site_rating.set("default", "true")
                xmlET.SubElement(site_rating, "value").text = str(row.get("rating"))
        
        for writer in movie.get("writers", []):
            xmlET.SubElement(root, "credits").text = writer
            
        for director in movie.get("directors", []):            
            xmlET.SubElement(root, "director").text = director
            
        for genre in movie.get("genres", []):
            xmlET.SubElement(root, "genre").text = genre
        
        for tag in movie.get("labels", []):
            xmlET.SubElement(root, "tag").text = tag
        
        if get_actors == True:
            movie_actors = xmlET.SubElement(root, "actors")
            for actor in movie.get("actors", []):
                movie_actor = xmlET.SubElement(movie_actors, "actor")
                xmlET.SubElement(movie_actor, "name").text = actor.get("name")
                xmlET.SubElement(movie_actor, "role").text = actor.get("role")
                xmlET.SubElement(movie_actor, "order").text = str( actor.get("order") )
                xmlET.SubElement(movie_actor, "thumb").text = actor.get("thumb")
            
        for collection in movie.get("collections", []):
            movie_collection = xmlET.SubElement(root, "set")
            xmlET.SubElement(movie_collection, "name").text = collection
        
        # set the XML indent for prettifying
        xmlET.indent(root, level=0)
        ## convert XML to String
        content = xmlET.tostring(root, encoding="unicode", method="xml")
        save_path = os.path.join(movie.get("local_folders")[0], "movie.nfo")
        self.write_nfo_to_file(content, save_path)
    
    def generate_show_nfo(self, show, get_actors=True):
        
        """Create a NFO file content from a tv show."""
        # display tags that are not taken into account
        root = xmlET.Element("tvshow")

        for country in show.get("countries", []):
            xmlET.SubElement(root, "country").text = country
        
        if show.get("addedAt"):
            new_zone = show.get("addedAt").replace("T", " ").replace("Z", "")
            addedAt = datetime.strptime(new_zone, '%Y-%m-%d %H:%M:%S').replace(tzinfo=UTC)
            xmlET.SubElement(root, "dateadded").text = addedAt.strftime('%Y-%m-%d %H:%M:%S')
        
        if show.get("lastViewedAt"):
            new_zone = show.get("lastViewedAt").replace("T", " ").replace("Z", "")
            lastViewedAt = datetime.strptime(new_zone, '%Y-%m-%d %H:%M:%S').replace(tzinfo=UTC)
            xmlET.SubElement(root, "lastplayed").text = lastViewedAt.strftime('%Y-%m-%d %H:%M:%S')
        
        if show.get("originalTitle"):
            xmlET.SubElement(root, "originalTitle").text = show.get("originalTitle")
        
        if int(show.get("viewCount") or 0) > 0 or show.get("lastViewedAt"):
            xmlET.SubElement(root, "playcount").text = str(show.get("viewCount"))
            xmlET.SubElement(root, "watched").text = "true"
        
        if show.get("summary"):
            xmlET.SubElement(root, "plot").text = show.get("summary")
        
        if show.get("originallyAvailableAt"):
            released = show.get("originallyAvailableAt").split("T")[0]
            # validate it's a real date, keep as YYYY-MM-DD string
            released = datetime.strptime(released, '%Y-%m-%d').strftime('%Y-%m-%d')
            xmlET.SubElement(root, "releasedate").text = released
            xmlET.SubElement(root, "premiered").text = released
        
        if show.get("duration"):
            xmlET.SubElement(root, "runtime").text = str( int(show.get("duration")) // 60_000 )
        
        if show.get("titleSort"):
            xmlET.SubElement(root, "sorttitle").text = show.get("titleSort")
            
        if show.get("studio"):
            xmlET.SubElement(root, "studio").text = show.get("studio")
            
        if show.get("tagline"):
            xmlET.SubElement(root, "tagline").text = show.get("tagline")
            
        xmlET.SubElement(root, "title").text = show.get("title", "")
        
        for guid in show.get("guids", []):
            id_type = guid.get("type")
            id_value = guid.get("value")
            
            id_element = xmlET.SubElement(root, "uniqueid", type=id_type)
            id_element.text = id_value
            if id_type == "imdb":
                id_element.set("default", "true")
                xmlET.SubElement(root, "id").text = id_value
                xmlET.SubElement(root, "imdbid").text = id_value
            elif id_type == "tmdb":
                xmlET.SubElement(root, "tmdbid").text = id_value
            elif id_type == "tvdb":
                xmlET.SubElement(root, "tvdbid").text = id_value
            elif id_type == "mbid":
                xmlET.SubElement(root, "idmbid").text = id_value
        
        if show.get("year"):
            xmlET.SubElement(root, "year").text = str( show.get("year") )
            
        if show.get("contentRating"):
            cRating = show.get("contentRating").replace("fr/", "FR-").replace("-Unrated", "-U").replace("-TP", "-Tous publics")
            xmlET.SubElement(root, "mpaa").text = cRating
        
        ratings = show.get("ratings", [])
        if len(ratings) > 0:
            site_ratings = xmlET.SubElement(root, "ratings")
            for row in ratings:
                site_rating = xmlET.SubElement(site_ratings, "rating", name=row.get("site"), max="10")
                if row.get("site") == "imdb":
                    site_rating.set("default", "true")
                xmlET.SubElement(site_rating, "value").text = str(row.get("rating"))
            
        for genre in show.get("genres", []):
            xmlET.SubElement(root, "genre").text = genre
        
        for tag in show.get("labels", []):
            xmlET.SubElement(root, "tag").text = tag
        
        if get_actors == True:
            show_actors = xmlET.SubElement(root, "actors")
            for actor in show.get("actors", []):
                show_actor = xmlET.SubElement(show_actors, "actor")
                xmlET.SubElement(show_actor, "name").text = actor.get("name")
                xmlET.SubElement(show_actor, "role").text = actor.get("role")
                xmlET.SubElement(show_actor, "order").text = str( actor.get("order") )
                xmlET.SubElement(show_actor, "thumb").text = actor.get("thumb")
            
        for season_no, season in show.get("seasons", {}).items():
            title = season.get("title", "").lower()
            if "season" not in title and "series" not in title:
                named_season = xmlET.SubElement(root, "namedseason", number=str(season_no))
                named_season.text = season.get("title")
        
        # set the XML indent for prettifying
        xmlET.indent(root, level=0)
        ## convert XML to String
        content = xmlET.tostring(root, encoding="unicode", method="xml")
        save_path = os.path.join(show.get("local_folders")[0], "tvshow.nfo")
        self.write_nfo_to_file(content, save_path)
    
    def generate_season_nfo(self, season, save_path):
        
        """Create a NFO file content from a tv season. Not Required by Plex, but may become useful in the future"""
        # display tags that are not taken into account
        root = xmlET.Element("season")
        
        if season.get("index"):
            xmlET.SubElement(root, "seasonnumber").text = str(season.get("index", ""))            
        
        if season.get("title"):
            xmlET.SubElement(root, "title").text = season.get("title", "")
        
        if season.get("parentTitle"):
            xmlET.SubElement(root, "showtitle").text = season.get("parentTitle", "")
        
        if season.get("year"):
            xmlET.SubElement(root, "year").text = str(season.get("year", ""))
        
        if season.get("summary"):
            xmlET.SubElement(root, "plot").text = str(season.get("summary", ""))
        
        if season.get("originallyAvailableAt"):
            released = season.get("originallyAvailableAt").split("T")[0]
            # validate it's a real date, keep as YYYY-MM-DD string
            released = datetime.strptime(released, '%Y-%m-%d').strftime('%Y-%m-%d')
            xmlET.SubElement(root, "premiered").text = released
        
        for tag in movie.get("labels", []):
            xmlET.SubElement(root, "tag").text = tag
        
        ratings = season.get("ratings", [])
        if len(ratings) > 0:
            site_ratings = xmlET.SubElement(root, "ratings")
            for row in ratings:
                site_rating = xmlET.SubElement(site_ratings, "rating", name=row.get("site"), max="10")
                if row.get("site") == "imdb":
                    site_rating.set("default", "true")
                xmlET.SubElement(site_rating, "value").text = str(row.get("rating"))
        
        for guid in season.get("guids", []):
            id_type = guid.get("type")
            id_value = guid.get("value")
            
            id_element = xmlET.SubElement(root, "uniqueid", type=id_type)
            id_element.text = id_value
            if id_type == "imdb":
                id_element.set("default", "true")
                xmlET.SubElement(root, "id").text = id_value
                xmlET.SubElement(root, "imdbid").text = id_value
            elif id_type == "tmdb":
                xmlET.SubElement(root, "tmdbid").text = id_value
            elif id_type == "tvdb":
                xmlET.SubElement(root, "tvdbid").text = id_value
            elif id_type == "mbid":
                xmlET.SubElement(root, "idmbid").text = id_value
        
        # set the XML indent for prettifying
        xmlET.indent(root, level=0)
        ## convert XML to String
        content = xmlET.tostring(root, encoding="unicode", method="xml")
        save_path = os.path.join(save_path, "season.nfo")
        self.write_nfo_to_file(content, save_path)
    
    def generate_episode_nfo(self, episode, save_path, save_filename, get_actors=True):
        
        """Create a NFO file content from a tv episode."""
        # display tags that are not taken into account
        root = xmlET.Element("episodedetails")
        
        if episode.get("addedAt"):
            new_zone = episode.get("addedAt").replace("T", " ").replace("Z", "")
            addedAt = datetime.strptime(new_zone, '%Y-%m-%d %H:%M:%S').replace(tzinfo=UTC)
            xmlET.SubElement(root, "dateadded").text = addedAt.strftime('%Y-%m-%d %H:%M:%S')
        
        if episode.get("lastViewedAt"):
            new_zone = episode.get("lastViewedAt").replace("T", " ").replace("Z", "")
            lastViewedAt = datetime.strptime(new_zone, '%Y-%m-%d %H:%M:%S').replace(tzinfo=UTC)
            xmlET.SubElement(root, "lastplayed").text = lastViewedAt.strftime('%Y-%m-%d %H:%M:%S')
        
        xmlET.SubElement(root, "title").text = episode.get("title", "")
        
        xmlET.SubElement(root, "season").text = episode.get("season_no", "")
        
        xmlET.SubElement(root, "episode").text = episode.get("episode_no", "")
        
        if int(episode.get("viewCount") or 0) > 0 or episode.get("lastViewedAt"):
            xmlET.SubElement(root, "playcount").text = str(episode.get("viewCount"))
        
        if int(episode.get("viewCount")) > 0 or episode.get("lastViewedAt"):
            xmlET.SubElement(root, "watched").text = "true"
        
        if episode.get("summary"):
            xmlET.SubElement(root, "plot").text = episode.get("summary")
        
        if episode.get("originallyAvailableAt"):
            released = episode.get("originallyAvailableAt").split("T")[0]
            # validate it's a real date, keep as YYYY-MM-DD string
            released = datetime.strptime(released, '%Y-%m-%d').strftime('%Y-%m-%d')
            xmlET.SubElement(root, "aired").text = released
        
        if episode.get("duration"):
            xmlET.SubElement(root, "runtime").text = str( int(episode.get("duration")) // 60_000 )
        
        if episode.get("titleSort"):
            xmlET.SubElement(root, "sorttitle").text = episode.get("titleSort")

        if episode.get("year"):
            xmlET.SubElement(root, "year").text = str( episode.get("year") )
            
        if episode.get("contentRating"):
            cRating = episode.get("contentRating").replace("fr/", "FR-").replace("-Unrated", "-U").replace("-TP", "-Tous publics")
            xmlET.SubElement(root, "mpaa").text = cRating
        
        for writer in episode.get("writers", []):
            xmlET.SubElement(root, "credits").text = writer
            
        for director in episode.get("directors", []):
            xmlET.SubElement(root, "director").text = director
        
        if get_actors == True:
            episode_actors = xmlET.SubElement(root, "actors")
            for actor in episode.get("actors", []):
                episode_actor = xmlET.SubElement(episode_actors, "actor")
                xmlET.SubElement(episode_actor, "name").text = actor.get("name")
                xmlET.SubElement(episode_actor, "role").text = actor.get("role")
                xmlET.SubElement(episode_actor, "order").text = str( actor.get("order") )
                xmlET.SubElement(episode_actor, "thumb").text = actor.get("thumb")
            
        
        # set the XML indent for prettifying
        xmlET.indent(root, level=0)
        ## convert XML to String
        content = xmlET.tostring(root, encoding="unicode", method="xml")
        save_path = os.path.join(save_path, str(save_filename) + ".nfo")
        self.write_nfo_to_file(content, save_path)
    
    def write_nfo_to_file(self, content, save_path):
        try:            
            with open(save_path, "w", encoding="utf-8") as file:
                file.write('<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n<!--created by PlexNFOPro for PLEX-->\n' + content)
            rtn = "OK"
        except Exception as err:
            rtn = f"FAILED ({err})"
        print(f"{save_path}: {rtn}")

            
