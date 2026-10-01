from PyQt6 import QtWidgets, sip
from PyQt6.QtWidgets import QWidget

import requests
import re, string
import ui.settings as settingsUIDialog
import ui.folder_widget as folderWidget
from includes.file_manager import PlexNFOFileManager
from plexapi.server import PlexServer
from plexapi.exceptions import Unauthorized, BadRequest


class PlexNFOProSettings():
    def __init__(self):
        self.fileManager = PlexNFOFileManager()
        self.home = self.fileManager.home                                                                   ## set the home directory for saving        
        self.init_settings_ui()                                                                             ## init the UI
        self._folderList = {}                                                                               ## set the folders list dict
        self.store = None                                                                                   ## used to store settings in memory
        self.settingsUI.settingsActions.accepted.disconnect()                                               ## remove Designer's default accept() hookup
        self.settingsUI.settingsActions.accepted.connect(self.save_settings)                                ## add pyqt signal for saving settings
        self.settingsUI.settingsActions.rejected.connect(self.close)
        self.settingsUI.addMovieFolderButton.clicked.connect( lambda: self.add_local_folder('movie') )
        self.settingsUI.addTVFolderButton.clicked.connect( lambda: self.add_local_folder('show') )
        self.get_settings()
    
    def init_settings_ui(self):
        self.FolderWidgets = {}
        self.FolderWidgets['show'] = {}
        self.FolderWidgets['movie'] = {}
        self.settingsUI = settingsUIDialog.Ui_Settings()
        self.settingsDialog = QtWidgets.QDialog()
        self.settingsUI.setupUi(self.settingsDialog)
        
    def load_folder_widgets_from_settings(self, folder_settings):
        self.clear_folders_from_settings() ## first clear the folders to reload them again
        for ftype, flist in folder_settings.items():
            if ftype == "movie":
                layout = self.settingsUI.movieFoldersVLayout
            else:
                layout = self.settingsUI.tvFoldersVLayout
            for fid, fdata in flist.items():
                layout.addWidget( self.create_folder_widget(ftype, fdata) )
    
    
    def get_settings(self, refresh=False):
        if self.store == None or refresh == True:
            self.store = self.fileManager.load_settings()
        return self.store
    
    def load_folders_list(self):
        settings = self.get_settings()
        return settings['folders']
    
    def get_plex_credentials(self):
        settings = self.get_settings()
        return settings['plexURL'], settings['plexToken']
    
    def load_settings(self):
        settings = self.get_settings()
        if settings:
            self.settingsUI.plexURLEdit.setText( settings.get('plexURL') )
            self.settingsUI.plexTokenEdit.setText( settings.get('plexToken') )
            
            if settings.get('downloadNFO') == True:
                self.settingsUI.downloadNFOCheckBox.setChecked( True )
            if settings.get('downloadPoster') == True:
                self.settingsUI.downloadPosterCheckBox.setChecked( True )
            if settings.get('downloadLogo') == True:
                self.settingsUI.downloadLogoCheckBox.setChecked( True )
            if settings.get('downloadBackground') == True:
                self.settingsUI.downloadBackgroundCheckBox.setChecked( True )
            if settings.get('downloadSquare') == True:
                self.settingsUI.downloadSquareCheckBox.setChecked( True )
            if settings.get('downloadEpisodeNFO') == True:
                self.settingsUI.downloadEpisodeNFOCheckBox.setChecked( True )
            if settings.get('downloadEpisodeThumb') == True:
                self.settingsUI.downloadEpisodeThumbCheckBox.setChecked( True )
            if settings.get('downloadSeasonNFO') == True:
                self.settingsUI.downloadSeasonNFOCheckBox.setChecked( True )
            if settings.get('downloadSeasonPoster') == True:
                self.settingsUI.downloadSeasonPosterCheckBox.setChecked( True )
            if settings.get('downloadSeasonBackground') == True:
                self.settingsUI.downloadSeasonBackgroundCheckBox.setChecked( True )
            if settings.get('downloadTheme') == True:
                self.settingsUI.downloadThemeCheckBox.setChecked( True )
            
            if settings.get('overwriteNFO') == True:
                self.settingsUI.overwriteNFOCheckBox.setChecked( True )
            if settings.get('overwritePoster') == True:
                self.settingsUI.overwritePosterCheckBox.setChecked( True )
            if settings.get('overwriteLogo') == True:
                self.settingsUI.overwriteLogoCheckBox.setChecked( True )
            if settings.get('overwriteBackground') == True:
                self.settingsUI.overwriteBackgroundCheckBox.setChecked( True )
            if settings.get('overwriteSquare') == True:
                self.settingsUI.overwriteSquareCheckBox.setChecked( True )
            if settings.get('overwriteEpisodeNFO') == True:
                self.settingsUI.overwriteEpisodeNFOCheckBox.setChecked( True )
            if settings.get('overwriteEpisodeThumb') == True:
                self.settingsUI.overwriteEpisodeThumbCheckBox.setChecked( True )
            if settings.get('overwriteSeasonNFO') == True:
                self.settingsUI.overwriteSeasonNFOCheckBox.setChecked( True )
            if settings.get('overwriteSeasonPoster') == True:
                self.settingsUI.overwriteSeasonPosterCheckBox.setChecked( True )
            if settings.get('overwriteSeasonBackground') == True:
                self.settingsUI.overwriteSeasonBackgroundCheckBox.setChecked( True )
            if settings.get('overwriteTheme') == True:
                self.settingsUI.overwriteThemeCheckBox.setChecked( True )
            
            if settings.get('saveActors') == True:
                self.settingsUI.saveActorsCheckBox.setChecked( True )
             
            self.load_folder_widgets_from_settings( settings.get('folders') )
    
    def save_settings(self):
        #print("Saving Settings")
        plexURL = self.settingsUI.plexURLEdit.text()
        plexToken = self.settingsUI.plexTokenEdit.text()
        
        ok, message = self.check_plex_credentials(plexURL, plexToken)
        if not ok:
            answer = QtWidgets.QMessageBox.warning(
                self.settingsDialog,
                "Plex Connection Failed",
                f"{message}\n\nSave these settings anyway?",
                QtWidgets.QMessageBox.StandardButton.Save | QtWidgets.QMessageBox.StandardButton.Cancel,
                QtWidgets.QMessageBox.StandardButton.Cancel
            )
            if answer == QtWidgets.QMessageBox.StandardButton.Cancel:
                return  ## stay in the settings window so they can fix it
        
        ## download options
        downloadNFO = self.settingsUI.downloadNFOCheckBox.isChecked()
        downloadPoster = self.settingsUI.downloadPosterCheckBox.isChecked()
        downloadLogo = self.settingsUI.downloadLogoCheckBox.isChecked()
        downloadBackground = self.settingsUI.downloadBackgroundCheckBox.isChecked()
        downloadSquare = self.settingsUI.downloadSquareCheckBox.isChecked()
        downloadEpisodeNFO = self.settingsUI.downloadEpisodeNFOCheckBox.isChecked()
        downloadEpisodeThumb = self.settingsUI.downloadEpisodeThumbCheckBox.isChecked()
        downloadSeasonNFO = self.settingsUI.downloadSeasonNFOCheckBox.isChecked()
        downloadSeasonPoster = self.settingsUI.downloadSeasonPosterCheckBox.isChecked()
        downloadSeasonBackground = self.settingsUI.downloadSeasonBackgroundCheckBox.isChecked()
        downloadTheme = self.settingsUI.downloadThemeCheckBox.isChecked()
        
        ## overwrite options
        overwriteNFO = self.settingsUI.overwriteNFOCheckBox.isChecked()
        overwritePoster = self.settingsUI.overwritePosterCheckBox.isChecked()
        overwriteLogo = self.settingsUI.overwriteLogoCheckBox.isChecked()
        overwriteBackground = self.settingsUI.overwriteBackgroundCheckBox.isChecked()
        overwriteSquare = self.settingsUI.overwriteSquareCheckBox.isChecked()
        overwriteEpisodeNFO = self.settingsUI.overwriteEpisodeNFOCheckBox.isChecked()
        overwriteEpisodeThumb = self.settingsUI.overwriteEpisodeThumbCheckBox.isChecked()
        overwriteSeasonNFO = self.settingsUI.overwriteSeasonNFOCheckBox.isChecked()
        overwriteSeasonPoster = self.settingsUI.overwriteSeasonPosterCheckBox.isChecked()
        overwriteSeasonBackground = self.settingsUI.overwriteSeasonBackgroundCheckBox.isChecked()
        overwriteTheme = self.settingsUI.overwriteThemeCheckBox.isChecked()
        
        # Save the actors in NFO
        saveActors = self.settingsUI.saveActorsCheckBox.isChecked()
        
        save_data = {
            "plexURL": f"{plexURL}",
            "plexToken": f"{plexToken}",
            "downloadNFO": downloadNFO,
            "downloadPoster": downloadPoster,
            "downloadLogo": downloadLogo,
            "downloadBackground": downloadBackground,
            "downloadSquare": downloadSquare,
            "downloadEpisodeNFO": downloadEpisodeNFO,
            "downloadEpisodeThumb": downloadEpisodeThumb,
            "downloadSeasonNFO": downloadSeasonNFO,
            "downloadSeasonPoster": downloadSeasonPoster,
            "downloadSeasonBackground": downloadSeasonBackground,
            "downloadTheme": downloadTheme,
            "overwriteNFO": overwriteNFO,
            "overwritePoster": overwritePoster,
            "overwriteLogo": overwriteLogo,
            "overwriteBackground": overwriteBackground,
            "overwriteSquare": overwriteSquare,
            "overwriteEpisodeNFO": overwriteEpisodeNFO,
            "overwriteEpisodeThumb": overwriteEpisodeThumb,
            "overwriteSeasonNFO": overwriteSeasonNFO,
            "overwriteSeasonPoster": overwriteSeasonPoster,
            "overwriteSeasonBackground": overwriteSeasonBackground,
            "overwriteTheme": overwriteTheme,
            "saveActors": saveActors,
            "folders": self._folderList
        }
        self.fileManager.save_settings(save_data)
        self.get_settings(True) ## recall to save settings back into memory after save
        self.settingsDialog.accept()  ## close the window now that we're done
        
    def select_folder(self, pwindow=None):
        folderpath = QtWidgets.QFileDialog.getExistingDirectory(pwindow, 'Select Folder')
        #print("Folder:", folderpath)
        return folderpath
    
    def create_folder_id(self, fname):
        wid = fname.replace(" ", "_")
        re.sub(r'\W+', '', wid)
        #print("WID", wid)
        return wid
    
    def clear_folders_from_settings(self):
        for ftype in list(self.FolderWidgets):
            for wid in list(self.FolderWidgets[ftype]):
                #print("CLEAR FTYPE", ftype)
                #print("CLEAR WID", wid)
                self.delete_folder_widget(ftype, wid)
            
    def delete_folder_widget(self, ftype, wid):
        self.settingsUI.movieFoldersVLayout.removeWidget(self.FolderWidgets[ftype][wid])
        sip.delete(self.FolderWidgets[ftype][wid])
        del self.FolderWidgets[ftype][wid]
        del self._folderList[ftype][wid]
        
    def create_folder_widget(self,ftype,fdata):
        #print("Folder: "+ ftype, fdata)
        
        if not self.FolderWidgets[ftype]:
            #print(f"Folder type {ftype} not found, creating folder widget type..")
            self.FolderWidgets[ftype] = {}
            self._folderList[ftype] = {}
            
        wid = self.create_folder_id(fdata['name'])  
        #print(f"New Folder ID: {wid}")
        
        self.FolderWidgets[ftype][wid] = QWidget()
        widget = folderWidget.Ui_folderWidget()
        widget.setupUi(self.FolderWidgets[ftype][wid])
        widget.folderLabel.setText(fdata['name'])
        widget.folderPathLabel.setText(fdata['path'])
        widget.deleteButton.clicked.connect(lambda checked=False, t=ftype, i=wid: self.delete_folder_widget(t, i))
        
        self._folderList[ftype][wid] = {"wid": f"{wid}", "type": f"{ftype}", "name": f"{fdata['name']}", "path": f"{fdata['path']}", "psplit": fdata['psplit']}
        
        return self.FolderWidgets[ftype][wid]
    
    def add_local_folder(self, ftype="movie"):
        folder = self.select_folder()
        if folder != "":
            fsplit = folder.split("/")
            folder_name = fsplit[-1]
            fdata={"name":f"{folder_name}","path":f"{folder}","psplit":fsplit}
            if ftype == "movie":
                self.settingsUI.movieFoldersVLayout.addWidget(self.create_folder_widget("movie",fdata))
            else:
                self.settingsUI.tvFoldersVLayout.addWidget(self.create_folder_widget("show",fdata))
    
    def check_plex_credentials(self, plexURL, plexToken):
        """Returns (True, "") if the credentials work, otherwise (False, reason)."""
        if not plexURL or not plexToken:
            return False, "Please enter both the Plex URL and the Plex token."
        try:
            PlexServer(plexURL, plexToken, timeout=5)
        except Unauthorized:
            return False, "The Plex token was rejected. Please check it and try again."
        except (requests.exceptions.MissingSchema, requests.exceptions.InvalidSchema):
            return False, "The Plex URL is invalid. It should look like http://192.168.1.10:32400"
        except requests.exceptions.Timeout:
            return False, "The Plex server took too long to respond."
        except requests.exceptions.ConnectionError:
            return False, "Could not reach the Plex server. Check the URL and that the server is running."
        except BadRequest as e:
            return False, f"Plex rejected the request: {e}"
        except Exception as e:
            return False, f"Could not connect to Plex: {e}"
        return True, ""
    
    def close(self):
        #print("Settings Closed !!!!!")
        self.settingsDialog.done(0)
    
    def _open(self):
        ## load the user settings
        self.load_settings()
        ## open the dialog window
        self.settingsDialog.exec()