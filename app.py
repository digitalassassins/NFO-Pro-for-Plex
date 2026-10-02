import sys
from PyQt6 import QtCore, QtGui, QtWidgets, sip
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget
#from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import QTimer, QObject, QThread, pyqtSignal
import os
import time
import images.images
import hashlib
from includes.settings import PlexNFOProSettings
from includes.scanner import PlexNFOScanner
from includes.file_manager import PlexNFOFileManager
from includes.plex_api_manager import PlexNFOPlexAPIManager
from includes.progress_calculator import ProgressCalculator
from includes.background_scaler import BackgroundScaler

from includes.image_manager import ImageLoadWorker

import ui.main as main
import ui.donate as donate

import ui.item_widget as itemWidget
import ui.no_items_widget as noItemWidget
import ui.season_widget as tvSeasonWidget

## testing
from random import randrange

class WidgetUpdateWorker(QObject):
    finished = pyqtSignal()         # emit job finished
    progress = pyqtSignal(int)      # emit the progress int value
    itemReady = pyqtSignal(list, str)   # emit data [batch_list, item_type=movie|show]

    def __init__(self, action, fileManager=None):
        super().__init__()
        self.action = action
        self.fileManager = fileManager
        self.dump_emit_count = 10

    def load_library_row_widgets(self, library_id, library_type, file_list = []):
        item_list = []
        if len(file_list) == 0:
            ## no pre sent filter list sent so we get all library json files
            file_list = self.fileManager.list_files_in_dir(os.path.join( ".cache", str(library_id) ,"data"), "json")
            
        self.percent = ProgressCalculator( len(file_list) ) ## work out the percentage
        for json_file in file_list:
            jfile = os.path.split(json_file)[1] ## remove the extension to be re-added in file manager class
            ## load the item data from the json file
            item_data = self.fileManager.load_library_directory_json( str(library_id), jfile )
            if item_data:
                ## add to the percentage
                self.progress.emit( self.percent.add() )
                item_list.append(item_data)
                if len(item_list) == self.dump_emit_count:
                    self.itemReady.emit(item_list, library_type) # send the data, plus if its filtered data or not
                    item_list = []
        
        ## flush any remaining items not sent in for loop
        if len(item_list) > 0:
            self.itemReady.emit(item_list, library_type) # send the data, plus if its filtered data or not
            item_list = []
        
    def run(self, library_id, library_type="movie", file_list=[]):
        if self.action == "Load":
            self.load_library_row_widgets(library_id, library_type, file_list)
        self.finished.emit()
    
class PlexNFOPro(QMainWindow):
    
    loadImagesRequested = pyqtSignal(list) # Emitting this hands a batch of images off to the persistent image worker thread to load images into GUI.
    switchCacheLibrary = pyqtSignal(int) # Emitting this changes the active cache library folder for the image worker to change cache library folder
    
    def __init__(self):
        super().__init__()
        self.close_installer_splash()
        self.fileManager = PlexNFOFileManager()
        self.settings = PlexNFOProSettings()
        self.scanner = PlexNFOScanner(self.settings)
        
        ## Stylesheets
        self._STYLESHEETS = {}
        self._STYLESHEETS["missing_tab_yes"] = "QWidget{    background-color: rgb(0, 170, 0);   border-top-right-radius: 6px;	border-bottom-right-radius: 6px;} QWidget QLabel{	color: rgb(255, 255, 255); }"
        self._STYLESHEETS["missing_tab_no"] = "QWidget{ background-color: rgb(216, 138, 37); border-top-right-radius: 6px;	border-bottom-right-radius: 6px; } QWidget QLabel{ color: rgb(255, 255, 255); }"
        self._STYLESHEETS["main_menu_orange"] = "QAbstractButton{ color:#d88a25; }"
        
        ## Static Icons
        self._ICONS = {}
        self._ICONS["chevron_down"] = QtGui.QIcon()
        self._ICONS["chevron_down"].addPixmap(QtGui.QPixmap(":/images/chevron_down_icon.png"), QtGui.QIcon.Mode.Normal, QtGui.QIcon.State.Off)
        self._ICONS["chevron_up"] = QtGui.QIcon()
        self._ICONS["chevron_up"].addPixmap(QtGui.QPixmap(":/images/chevron_up_icon.png"), QtGui.QIcon.Mode.Normal, QtGui.QIcon.State.Off)
        
        self.init_main_ui()
        self.init_donate_ui()
        
        ## add the no items widget for when no items are found during search and filtering
        self.add_no_items_widget()
        ## add a stretch to the scroll are to push items to the top
        self.mainUI.scrollAreaWidgetContentsVLayout.addStretch() # add a stretch to scroll area to push content to the top
        self.mainUI.mainScrollArea.setWidgetResizable(True)
        self.mainUI.mainScrollArea.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft) # set the scroll area to vertically align top
        
        self.RowWidgets = {}
        
        self._active_threads = []  # keep refs so QThreads aren't GC'd mid-run, used for the Movie and TV Widget Loader
        self.library_filters = {}
        self.load_generation = 0
        self.download_batch_running = False
        self.current_downloading_iwid = None
        self.current_library_id = None
        self.current_library_type = None
        self.search_list = {}
        
        ## set up the image loader thread
        self.image_thread = QThread()
        self.image_worker = ImageLoadWorker()
        self.image_worker.moveToThread(self.image_thread)
        self.loadImagesRequested.connect(self.image_worker.process_images)
        self.switchCacheLibrary.connect(self.image_worker.switch_library)
        self.image_worker.imagesReady.connect(self.update_batch_images_in_ui)
        self.image_thread.start()
        
        ## set up the buttons
        self.mainUI.settingsButton.clicked.connect(self.open_settings)
        self.mainUI.scanButton.clicked.connect(self.open_scan)
        self.mainUI.searchButton.clicked.connect(self.search_library)
        self.mainUI.searchLineEdit.returnPressed.connect(self.search_library)
        self.mainUI.searchLineEdit.textChanged.connect(self.search_library)
        self.mainUI.downloadAllButton.clicked.connect(self.download_all_items)
        self.mainUI.donateButton.clicked.connect(self.open_donate)
        
        ## build the menu if we have sections downloaded
        self.MenuButtons = {}
        self.menu_first_init = True
        self.build_main_menu()
        self.create_filter_combo_box()
        
        ## set up to rescan when the settings page has been closed
        self.scanner.scannerDialog.finished.connect(self.scan_library_sections) 
    
    def close_installer_splash(self):
        try:
            import pyi_splash
            pyi_splash.update_text('UI Loaded ...')
            pyi_splash.close()
        except:
            pass
    
    def buy_us_a_coffee(self):
        import webbrowser
        from cryptography.fernet import Fernet
        kS = ["Y44hH0iJ80tw4GrkaIYiZT-2wZABl_D4T7cE9-e5EOw=", "gAAAAABqvgoWUQKMbSe0lpMO-MTa5xhaQ9zZSsXIt4BPWmgnzWjwoaSGH5WM9NW7PCmDAwH76nPdsvFLcZEHAntAteI5sXD9E1deaF-PTiea7a-XSIp9Cy0gOyrEHdC-BdE5Ft3cVe4BLfOCcQNE8L4NcRy98M4aZQ=="]; fernet = Fernet(kS[0]);
        webbrowser.open(fernet.decrypt(kS[1]).decode(), new=0, autoraise=True)
    
    def init_donate_ui(self):
        # initialise the main menu
        self.donateUI = donate.Ui_Donate()
        self.donateDialog = QtWidgets.QDialog()
        self.donateUI.setupUi(self.donateDialog)
        self.donateUI.donateButton.clicked.connect(self.buy_us_a_coffee)
        
    def init_main_ui(self):
        # initialise the main menu
        self.mainUI = main.Ui_MainWindow()
        self.mainUI.setupUi(self)
  
    def first_init_load(self, library_id, ltype):
        if self.menu_first_init == True:
            if ltype == "movie":
                self.load_movie_widgets(library_id)
            else:
                self.load_tv_show_widgets(library_id)
            self.current_library_id = library_id
            self.current_library_type = ltype
            self.menu_first_init = False
    
    def open_settings(self):
        ## open the settings dialog
        self.settings._open()
    
    def open_scan(self):
        ## open the scanner dialog
        self.scanner._open()
    
    def open_donate(self):
        ## open the donate dialog
        self.donateDialog.exec()
    
    def scan_library_sections(self):
        ## build the main menu again if needed
        items, total = self.scanner.start_library_section_scan()
        if total > 0:
            self.build_main_menu()

    def clear_scroll_area(self):
        ''' clears the scroll are of widgets '''
        self.load_generation += 1
        self.delete_movie_widgets()
        self.delete_tv_show_widgets()

    def disable_controls_during_load(self):
        self.mainUI.searchLineEdit.setEnabled(False)
        self.mainUI.searchButton.setEnabled(False)
        self.mainUI.filterComboBox.setEnabled(False)
        self.mainUI.downloadAllButton.setEnabled(False)
        self.mainUI.settingsButton.setEnabled(False)
    
    def enable_controls_after_load(self):
        self.mainUI.searchLineEdit.setEnabled(True)
        self.mainUI.searchButton.setEnabled(True)
        self.mainUI.filterComboBox.setEnabled(True)
        self.mainUI.downloadAllButton.setEnabled(True)
        self.mainUI.settingsButton.setEnabled(True)
    

    ##################################################
    #######
    #######              Progress
    #######
    ##################################################
    
    def show_scan_progress(self, percent):
        self.mainUI.mainProgressBar.setValue(percent)
    
    def update_main_progress_bar(self, percent):
        #print(str(percent) + " %")
        if percent > 0 and percent < 100:
            self.mainUI.mainProgressBar.setVisible(True)
            self.mainUI.mainProgressBar.setValue(percent)
        else:
            self.mainUI.mainProgressBar.setVisible(False)
            self.mainUI.mainProgressBar.setValue(0)


    ##################################################
    #######
    #######                Menu
    #######
    ##################################################
    
    
    def build_main_menu(self, sections=None): ## can pass the sections in from the plex server scan to rebuild the menu
        self.clear_main_menu()
        if not sections:
            sections = self.fileManager.load_saved_sections()
        first_section=True
        first_key = None
        first_type = None
        
        if sections:
            #print("Sections:", sections)
            for key in sections:
                for section in sections[key]:
                    if section["matched"] == True:
                        if first_section == True:
                            first_key = section["key"] ## get the first section to load on init
                            first_type = section["type"] ## get the first section to load on init
                            first_section = False
                        self.create_menu_button(section["type"], section["key"], section["title"], section["uuid"])        
        if first_key and first_type:
            self.first_init_load(first_key, first_type) ## load the first section in on load
                
    def clear_main_menu(self):
        for key in list(self.MenuButtons):
            self.mainUI.sectionButtonsVLayout.removeWidget(self.MenuButtons[key])
            sip.delete(self.MenuButtons[key]) ## reset the movie widgets to nothing
        self.MenuButtons = {}
    
    def create_menu_button(self, mtype, mid, title, uuid):
        ## create the icon
        icon = QtGui.QIcon()
        if mtype == "movie":
            icon.addPixmap(QtGui.QPixmap(":/images/movie_icon.png"), QtGui.QIcon.Mode.Normal, QtGui.QIcon.State.Off)
        else:
            icon.addPixmap(QtGui.QPixmap(":/images/tv_icon.png"), QtGui.QIcon.Mode.Normal, QtGui.QIcon.State.Off)
        ## compile the menu button    
        self.MenuButtons[mid] = {}        
        self.MenuButtons[mid] = QtWidgets.QPushButton(parent=self.mainUI.menuWidget)
        self.MenuButtons[mid].setStyleSheet(self._STYLESHEETS["main_menu_orange"])
        self.MenuButtons[mid].setIcon(icon)
        self.MenuButtons[mid].setIconSize(QtCore.QSize(20, 20))
        self.MenuButtons[mid].setFlat(True)
        self.MenuButtons[mid].setObjectName( "menuButton_"+str(mid) )
        self.MenuButtons[mid].setText(title)
        self.mainUI.sectionButtonsVLayout.addWidget(self.MenuButtons[mid])
        ## add the click function based on what type of section it is
        if mtype == "movie":
            self.MenuButtons[mid].clicked.connect(lambda: self.load_movie_widgets(mid))
        else:
            self.MenuButtons[mid].clicked.connect(lambda: self.load_tv_show_widgets(mid))

    ##################################################
    #######
    #######         No Items Widget
    #######
    ##################################################
    
    def hide_no_items_widget(self):
        self.emptyRowWidget.setVisible(False)
        
    def show_no_items_widget(self):
        self.emptyRowWidget.setVisible(True)
    
    def add_no_items_widget(self):
        self.emptyRowWidget = QWidget()
        widget = noItemWidget.Ui_noItemsWidget()
        widget.setupUi(self.emptyRowWidget)
        self.emptyRowWidget.ui = widget
        self.mainUI.scrollAreaWidgetContentsVLayout.addWidget(self.emptyRowWidget)
        self.hide_no_items_widget()


    ##################################################
    #######
    #######         Movies / Show Helpers
    #######
    ##################################################

    def update_row_widget_title_text(self, iwid, title):
        self.RowWidgets[iwid].ui.itemName.setText(title)
    
    def update_row_widget_year_text(self, iwid, year):
        self.RowWidgets[iwid].ui.itemYear.setText(str(year))
        
    def update_row_widget_poster_missing_text(self, iwid, poster_file):
        self.RowWidgets[iwid].ui.posterMissing.setText('<a href="file:///'+ poster_file +'">Yes</a>')
        self.RowWidgets[iwid].ui.posterMissing.setOpenExternalLinks(True)
        self.RowWidgets[iwid].ui.posterMissingWidget.setStyleSheet(self._STYLESHEETS["missing_tab_yes"])
    
    def update_row_widget_nfo_missing_text(self, iwid, nfo_file):
        self.RowWidgets[iwid].ui.nfoMissing.setText('<a href="file:///'+ nfo_file +'">Yes</a>')
        self.RowWidgets[iwid].ui.nfoMissing.setOpenExternalLinks(True)
        self.RowWidgets[iwid].ui.nfoMissingWidget.setStyleSheet(self._STYLESHEETS["missing_tab_yes"])
    
    def update_row_widget_poster_missing_text(self, iwid, poster_file):
        self.RowWidgets[iwid].ui.posterMissing.setText('<a href="file:///'+ poster_file +'">Yes</a>')
        self.RowWidgets[iwid].ui.posterMissing.setOpenExternalLinks(True)
        self.RowWidgets[iwid].ui.posterMissingWidget.setStyleSheet(self._STYLESHEETS["missing_tab_yes"])
    
    def update_row_widget_background_missing_text(self, iwid, background_file):
        self.RowWidgets[iwid].ui.backgroundMissing.setText('<a href="file:///'+ background_file +'">Yes</a>')
        self.RowWidgets[iwid].ui.backgroundMissing.setOpenExternalLinks(True)
        self.RowWidgets[iwid].ui.backgroundMissingWidget.setStyleSheet(self._STYLESHEETS["missing_tab_yes"])
    
    def update_row_widget_logo_missing_text(self, iwid, logo_file):
        self.RowWidgets[iwid].ui.logoMissing.setText('<a href="file:///'+ logo_file +'">Yes</a>')
        self.RowWidgets[iwid].ui.logoMissing.setOpenExternalLinks(True)
        self.RowWidgets[iwid].ui.logoMissingWidget.setStyleSheet(self._STYLESHEETS["missing_tab_yes"])
    
    def update_row_widget_square_missing_text(self, iwid, square_art_file):
        self.RowWidgets[iwid].ui.squareMissing.setText('<a href="file:///'+ square_art_file +'">Yes</a>')
        self.RowWidgets[iwid].ui.squareMissing.setOpenExternalLinks(True)
        self.RowWidgets[iwid].ui.squareMissingWidget.setStyleSheet(self._STYLESHEETS["missing_tab_yes"])
    
    def update_row_widget_theme_missing_text(self, iwid, theme_file):
        self.RowWidgets[iwid].ui.themeMissing.setText('<a href="file:///'+ theme_file +'">Yes</a>')
        self.RowWidgets[iwid].ui.themeMissing.setOpenExternalLinks(True)
        self.RowWidgets[iwid].ui.themeMissingWidget.setStyleSheet(self._STYLESHEETS["missing_tab_yes"])
    
    def update_row_nfo_status_widget_visibility(self, iwid, visible=False):
        self.RowWidgets[iwid].ui.nfoStatusWidget.setVisible(visible)
        self.RowWidgets[iwid].ui.serverNfoStatusWidget.setVisible(visible)
    
    def update_row_logo_status_widget_visibility(self, iwid, visible=False):
        self.RowWidgets[iwid].ui.logoStatusWidget.setVisible(visible)
        self.RowWidgets[iwid].ui.serverLogoStatusWidget.setVisible(visible)
    
    def update_row_poster_status_widget_visibility(self, iwid, visible=False):
        self.RowWidgets[iwid].ui.posterStatusWidget.setVisible(visible)
        self.RowWidgets[iwid].ui.serverPosterStatusWidget.setVisible(visible)
    
    def update_row_background_status_widget_visibility(self, iwid, visible=False):
        self.RowWidgets[iwid].ui.backgroundStatusWidget.setVisible(visible)
        self.RowWidgets[iwid].ui.serverBackgroundStatusWidget.setVisible(visible)
    
    def update_row_square_status_widget_visibility(self, iwid, visible=False):
        self.RowWidgets[iwid].ui.squareStatusWidget.setVisible(visible)
        self.RowWidgets[iwid].ui.serverSquareStatusWidget.setVisible(visible)
    
    def update_row_theme_status_widget_visibility(self, iwid, visible=False):
        self.RowWidgets[iwid].ui.themeStatusWidget.setVisible(visible)
        self.RowWidgets[iwid].ui.serverThemeStatusWidget.setVisible(visible)
    
    def update_row_status_labels_visibility(self, iwid, visible=False):
        self.RowWidgets[iwid].ui.serverLabel.setVisible(visible)
        self.RowWidgets[iwid].ui.localLabel.setVisible(visible)
    
    def update_row_status_visibility(self, iwid):
        
        downloadNFO = self.settings.store.get("downloadNFO", False)
        self.update_row_nfo_status_widget_visibility(iwid, downloadNFO)
        
        downloadPoster = self.settings.store.get("downloadPoster", False)
        self.update_row_poster_status_widget_visibility(iwid, downloadPoster)
        
        downloadBackground = self.settings.store.get("downloadBackground", False)
        self.update_row_background_status_widget_visibility(iwid, downloadBackground)
        
        downloadLogo = self.settings.store.get("downloadLogo", False)
        self.update_row_logo_status_widget_visibility(iwid, downloadLogo)
        
        downloadSquare = self.settings.store.get("downloadSquare", False)
        self.update_row_square_status_widget_visibility(iwid, downloadSquare)
        
        downloadTheme = self.settings.store.get("downloadTheme", False)
        self.update_row_theme_status_widget_visibility(iwid, downloadTheme)
        
        ## if any of them are true then display the server and local labels
        if [downloadNFO,downloadPoster,downloadBackground,downloadLogo,downloadSquare,downloadTheme].count(True) > 0:
            self.update_row_status_labels_visibility(iwid, True)
        else:
            self.update_row_status_labels_visibility(iwid, False)
    
    def add_batch_widget_from_data(self, item_list):
        ''' Used to batch load items into the GUI to slow down paint times'''
        for item in item_list:
            #print(item)
            self.add_item_widget_from_data(item)
        QApplication.processEvents()
        
    def add_item_widget_from_data(self, item):
        iwid = len(self.RowWidgets) + 1
        self.RowWidgets[iwid] = self.create_item_widget(iwid, item)
        self.mainUI.scrollAreaWidgetRowsVLayout.addWidget(self.RowWidgets[iwid])

    def set_all_widget_rows_visible(self):
        for key, widget in self.RowWidgets.items():
            widget.setVisible(True)
        self.hide_no_items_widget() ## hide the no items widget
        
    def set_all_widget_rows_hidden(self):
        for key, widget in self.RowWidgets.items():
            widget.setVisible(False)
        self.show_no_items_widget() ## show the no items widget

    def _on_thread_finished(self, pair):
        if pair in self._active_threads:
            self._active_threads.remove(pair)

    def disable_widget_controls_during_load(self):
        #print(self.RowWidgets.items())
        #print("Started Loading!!!")
        for key, widget in self.RowWidgets.items():
            widget.ui.refreshButton.setEnabled(False)
            widget.ui.itemDataDownloadButton.setEnabled(False)
        return
    
    def enable_widget_controls_after_load(self):
        #print("Finished Loading!!!")
        for key, widget in self.RowWidgets.items():
            widget.ui.refreshButton.setEnabled(True)
            widget.ui.itemDataDownloadButton.setEnabled(True)
        return
    
    def reset_row_status(self, iwid):
        
        ui = self.RowWidgets[iwid].ui

        ## local badges: nfoMissing / nfoMissingWidget, posterMissing / posterMissingWidget, ...
        for name in ["nfo", "poster", "background", "logo", "square", "theme"]:
            getattr(ui, name + "Missing").setText("No")
            getattr(ui, name + "MissingWidget").setStyleSheet(self._STYLESHEETS["missing_tab_no"])

        ## server badges: serverPosterMissing / serverPosterMissingWidget, ...
        for name in ["Poster", "Background", "Logo", "Square", "Theme"]:
            getattr(ui, "server" + name + "Missing").setText("No")
            getattr(ui, "server" + name + "MissingWidget").setStyleSheet(self._STYLESHEETS["missing_tab_no"])
        
        ## remove this row from every "missing" filter list; update_item_widget_data re-adds it where still missing
        for filter_type, ids in self.library_filters.items():
            if isinstance(ids, list):   # some entries are dicts keyed by library id, skip those
                ids[:] = [i for i in ids if i != iwid]
        
    def clear_row_images(self, iwid):
        row = self.RowWidgets[iwid]
        ## poster
        #row.ui.itemPoster.clear()
        row.ui.itemPoster.setPixmap(QtGui.QPixmap(":/images/no_image.jpg"))
        ## logo: itemName shows the logo image, so put the title text back
        row.ui.itemName.setText(row.data["title"])
        ## background: remove the old scaler so nothing paints the old image
        old_bg = getattr(row, "backgroundManager", None)
        if old_bg is not None:
            row.ui.backgroundDisplayWidget.removeEventFilter(old_bg)
            old_bg.deleteLater()
            row.backgroundManager = None
            row.ui.backgroundDisplayWidget.update()   # repaint without the old image
    
    def refresh_widget(self, iwid, on_done=None, retries=10):
        print("[refresh] called:", iwid,
          "| batch:", on_done is not None,
          "| button enabled:", self.RowWidgets[iwid].ui.refreshButton.isEnabled(),
          "| scanner busy:", self.scanner._busy)
        
        refreshButton = self.RowWidgets[iwid].ui.refreshButton
        dlButton = self.RowWidgets[iwid].ui.itemDataDownloadButton
        if not refreshButton.isEnabled():
            if on_done and retries > 0:  # part of a batch, so try again shortly instead of stalling
                print("[batch] refresh button disabled, retrying:", iwid)
                QTimer.singleShot(500, lambda: self.refresh_widget(iwid, on_done, retries - 1))
            elif on_done:
                print("[batch] gave up refreshing, moving on:", iwid)
                on_done()
            return
        
        def widget_refresh_redraw(riwid, item_data):
            #print("Item: ", item_data)
            self.RowWidgets[riwid].data = item_data # keep the stored data in sync
            self.clear_row_images(riwid) # refresh the images in the widget
            self.reset_row_status(riwid) # refresh the badges to show the new data
            self.update_item_widget_data(riwid, item_data, self.RowWidgets[riwid].ui)
        
        def single_item_progress_update(percent):
            self.RowWidgets[iwid].ui.progressBar.setValue(int(percent))
        
        def re_enable_button():
            print("[batch] refresh finished:", iwid)
            self.enable_widget_controls_after_load()
            if on_done:          # refresh is finished, buttons are enabled again
                on_done()
        
        ## scan single item
        started = self.scanner.single_item_scan(
            iwid, 
            self.RowWidgets[iwid].data, 
            update_widget_callback=widget_refresh_redraw, 
            single_item_progress_callback=single_item_progress_update,
            finished_callback=re_enable_button
        )
        if started:
            self.disable_widget_controls_during_load()
        elif on_done and retries > 0:
            print("[batch] scanner busy, retrying refresh:", iwid)
            QTimer.singleShot(500, lambda: self.refresh_widget(iwid, on_done))
        elif on_done:
            print("[batch] gave up refreshing, moving on:", iwid)
            on_done()
        
    def download_all_items(self):
        
        # Decide which rows to download BEFORE any download starts,
        # so rows getting disabled mid-download doesn't affect the list
        self.download_queue = [
            iwid for iwid, widget in self.RowWidgets.items()
            if widget.isVisible()
        ]
        self.download_batch_running = True
        self.current_downloading_iwid = None   # the item currently downloading
        self.download_next_item()
        
    def download_next_item(self):
        if not self.download_queue:
            self.download_batch_running = False
            self.current_downloading_iwid = None
            print("[batch] all downloads finished")
            return

        self.current_downloading_iwid = self.download_queue.pop(0)
        print("[batch] next item:", self.RowWidgets[self.current_downloading_iwid].data["title"])
        if not self.download_single_item(self.current_downloading_iwid):
            print("[batch] could not start, skipping:", self.RowWidgets[self.current_downloading_iwid].data["title"])
            self.download_next_item()
        
    def on_download_finished(self, iwid):
        # Only move on if this finish belongs to the batch's current item
        if self.download_batch_running and iwid == self.current_downloading_iwid:
            self.download_next_item()
    
    def download_single_item(self, iwid):
        dlButton = self.RowWidgets[iwid].ui.itemDataDownloadButton
        if not dlButton.isEnabled():
            print("[batch] download button disabled:", iwid)
            return False
        
        def refresh_callback():
            print("[batch] download finished, refreshing:", iwid)
            self.refresh_widget(iwid, on_done=lambda: self.on_download_finished(iwid))
            
        started = self.scanner.start_download_item(iwid=iwid, item=self.RowWidgets[iwid].data, finished_callback=refresh_callback)
        print("[batch] download started:", iwid, started)
        return started

    ##################################################
    #######
    #######             Movies
    #######
    ##################################################
    
    def update_item_widget_data(self, iwid, item_data, widget):
        image_list = []
        
        ############################################
        ### Get LOCAL Data and update the Widget ###
        ############################################ 
        
        #print("IWID:", iwid)
        #print("Item:", item_data)
        
        ## update what items are visisble
        self.update_row_status_visibility(iwid)
        
        ## hide the season dropdown for movies and link up button for shows
        if item_data.get("type") == "show":
            if not hasattr(self.RowWidgets[iwid], 'season_toggle'):
                self.RowWidgets[iwid].season_toggle=False            
            showSeasonsBtn = self.RowWidgets[iwid].ui.showSeasonsButton
            try:
                showSeasonsBtn.clicked.disconnect()
            except TypeError:
                pass  # nothing was connected yet, only disconnect on refresh
            showSeasonsBtn.clicked.connect(lambda: self.toggle_season_display(item_data, iwid))
        else:
            self.RowWidgets[iwid].ui.seasonHolderWidget.setVisible(False)
            
        
        ## check if item_data nfo file is listed
        if item_data.get('local_nfo', False):
            nfo_file = str( os.path.join(item_data['local_folders'][0], item_data['local_nfo']) ).replace("\\","/")
            self.update_row_widget_nfo_missing_text(iwid, nfo_file)
        else: ## add the item to the filter
            self.add_library_filter_item( "nfo", iwid)
        
        ## check item_data poster is listed
        if item_data.get('local_poster', False):
            poster = str( os.path.join(item_data['local_folders'][0], item_data['local_poster']) ).replace("\\","/")
            self.update_row_widget_poster_missing_text(iwid, poster)                
            image_list.append({ "wid":iwid, "image":poster, "image_type":"poster", "image_slug": item_data['slug'], "gen": self.load_generation })
        else: ## add the item to the filter
            self.add_library_filter_item( "poster", iwid)
        
        ## check item_data background is listed
        if item_data.get('local_background', False):
            background = str( os.path.join(item_data['local_folders'][0], item_data['local_background']) ).replace("\\","/")
            self.update_row_widget_background_missing_text(iwid, background)                
            image_list.append({ "wid":iwid, "image":background, "image_type":"background", "image_slug": item_data['slug'], "gen": self.load_generation })
        else: ## add the item to the filter
            self.add_library_filter_item( "background", iwid )
        
        ## check item_data logo is listed
        if item_data.get('local_logo', False):
            logo = str( os.path.join(item_data['local_folders'][0], item_data['local_logo']) ).replace("\\","/")
            self.update_row_widget_logo_missing_text(iwid, logo)
            image_list.append({ "wid":iwid, "image":logo, "image_type":"logo", "image_slug": item_data['slug'], "gen": self.load_generation })
        else: ## add the item to the filter
            self.add_library_filter_item( "logo", iwid)

        ## check item_data square is listed
        if item_data.get('local_square', False):
            square_art = str( os.path.join(item_data['local_folders'][0], item_data['local_square']) ).replace("\\","/")
            self.update_row_widget_square_missing_text(iwid, square_art)
        else: ## add the item to the filter
            self.add_library_filter_item( "square", iwid )
        
        
        ## check item_data square is listed
        if item_data.get('local_theme', False):
            theme = str( os.path.join(item_data['local_folders'][0], item_data['local_theme']) ).replace("\\","/")
            self.update_row_widget_theme_missing_text(iwid, theme)
        else: ## add the item to the filter
            self.add_library_filter_item( "theme", iwid )
            

        #############################################
        ### Get SERVER Data and update the Widget ###
        #############################################
        
        if self.settings.store.get("downloadPoster") == True:
            if item_data.get('server_poster'):
                widget.serverPosterMissing.setText('Yes')
                widget.serverPosterMissingWidget.setStyleSheet(self._STYLESHEETS["missing_tab_yes"])
        
        if self.settings.store.get("downloadBackground") == True:
            if item_data.get('server_background'):
                widget.serverBackgroundMissing.setText('Yes')
                widget.serverBackgroundMissingWidget.setStyleSheet(self._STYLESHEETS["missing_tab_yes"])
        
        if self.settings.store.get("downloadLogo") == True:
            if item_data.get('server_logo'):
                widget.serverLogoMissing.setText('Yes')
                widget.serverLogoMissingWidget.setStyleSheet(self._STYLESHEETS["missing_tab_yes"])
        
        if self.settings.store.get("downloadSquare") == True:
            if item_data.get('server_square'):
                widget.serverSquareMissing.setText('Yes')
                widget.serverSquareMissingWidget.setStyleSheet(self._STYLESHEETS["missing_tab_yes"])
        
        if self.settings.store.get("downloadTheme") == True:
            if item_data.get('theme'):
                widget.serverThemeMissing.setText('Yes')
                widget.serverThemeMissingWidget.setStyleSheet(self._STYLESHEETS["missing_tab_yes"])
        
        ## offload image loading and thumbnail generation to the image worker thread
        self.image_loader(image_list) ## pass the list of images to process to the image loader thread
        
        ## if the season is toggled open, update the season data aswell
        if item_data.get("type") == "show" and self.RowWidgets[iwid].season_toggle==True:
            for season_no, season in item_data.get("seasons",{}).items():
                self.update_tv_season_widget(iwid, str(season_no), season)

    def create_item_widget(self, iwid, item):
        ''' used to generate movie / tv show widgets, compile the filter list and then offload the images to the image loader thread '''
        self.search_list[iwid] = []
        self.RowWidgets[iwid] = QWidget()
        widget = itemWidget.Ui_itemWidget()
        widget.setupUi(self.RowWidgets[iwid])
        widget.refreshButton.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        widget.itemDataDownloadButton.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.RowWidgets[iwid].ui = widget
        self.RowWidgets[iwid].data = item
        widget.itemName.setText(item['title'])
        self.search_list[iwid].append(item['title'].lower())
        widget.itemYear.setText(str(item['year']))        
        
        ############################################
        ### update the Widget button connections ###
        ############################################        
        def download_progress_callback(progress):
            self.itemDownloadProgress[wid] = int(progress)
            
        widget.refreshButton.clicked.connect( lambda: self.refresh_widget(iwid) )
        widget.itemDataDownloadButton.clicked.connect( lambda: self.download_single_item(iwid) )
        
        ############################################
        ###  update the data inside the Widget   ###
        ############################################
        self.update_item_widget_data(iwid, item, widget)
        
        #self.loadImagesRequested.emit(image_list)
        return self.RowWidgets[iwid]

    '''def add_movie_widget_to_gui(self, wid):
        self.mainUI.scrollAreaWidgetRowsVLayout.addWidget(self.RowWidgets[wid])
    '''
    
    def load_movie_widgets(self, library_id, filter_list=[]):
        self.library_filters = {} ## reset the library filters
        self.search_list = {} # reset the search filters
        self.current_library_id = library_id
        self.current_library_type = "movie"
        #self.clear_filter_combo_items()
        if not filter_list:
            ## this is a full, unfiltered load - reset this library's filter
            ## lists so they get rebuilt fresh instead of growing every time
            self.library_filters[library_id] = {}
        self.disable_controls_during_load() ## disable the controls to prevent reloading
        
        self.switch_cache_library(self.current_library_id) ## switch the cache library
        self.clear_scroll_area()
        thread = QThread()
        worker = WidgetUpdateWorker("Load", self.fileManager)
        worker.moveToThread(thread)
        thread.started.connect(lambda: worker.run(self.current_library_id, "movie", filter_list))
        #worker.finished.connect(self.calculate_filter_items) ## calculate the filter combo items once progress is complete
        worker.finished.connect(self.enable_controls_after_load) ## calculate the filter combo items once progress is complete
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        worker.progress.connect(self.update_main_progress_bar)
        worker.itemReady.connect(self.add_batch_widget_from_data)  # receives a list of 10 items to prevent refreshing too fast
        # keep this pair alive until the thread actually finishes
        pair = (thread, worker)
        self._active_threads.append(pair)
        thread.finished.connect(lambda: self._on_thread_finished(pair))
        # start thread
        thread.start()

    def delete_movie_widgets(self):
        for key in list(self.RowWidgets):
            self.mainUI.scrollAreaWidgetRowsVLayout.removeWidget(self.RowWidgets[key])
            sip.delete(self.RowWidgets[key]) 
        self.RowWidgets = {} ## reset the movie widgets to nothing

    ''' def remove_movie_widget_from_gui(self, widget):
        self.mainUI.scrollAreaWidgetRowsVLayout.removeWidget(widget)
    '''

    ##################################################
    #######
    #######             TV Shows
    #######
    ##################################################
    
    def update_tv_season_widget(self, iwid, season_no, season):
        self.RowWidgets[iwid].SeasonWidgets[season_no].ui.seasonName.setText(season['title'])
        
        if season.get('server_poster'):
            self.RowWidgets[iwid].SeasonWidgets[season_no].ui.serverPosterMissing.setText('Yes')
            self.RowWidgets[iwid].SeasonWidgets[season_no].ui.serverPosterMissingWidget.setStyleSheet(self._STYLESHEETS["missing_tab_yes"])
        
        if season.get('server_background'):
            self.RowWidgets[iwid].SeasonWidgets[season_no].ui.serverBackgroundMissing.setText('Yes')
            self.RowWidgets[iwid].SeasonWidgets[season_no].ui.serverBackgroundMissingWidget.setStyleSheet(self._STYLESHEETS["missing_tab_yes"])
        
        if season.get('local_nfo'):
            nfo_file = str( os.path.join(season['local_folders'][0], season['local_nfo']) ).replace("\\","/")
            self.RowWidgets[iwid].SeasonWidgets[season_no].ui.nfoMissing.setText('<a href="file:///'+ str(nfo_file) +'">Yes</a>')
            self.RowWidgets[iwid].SeasonWidgets[season_no].ui.nfoMissing.setOpenExternalLinks(True)
            self.RowWidgets[iwid].SeasonWidgets[season_no].ui.nfoMissingWidget.setStyleSheet(self._STYLESHEETS["missing_tab_yes"])
        
        if season.get('local_poster'):
            poster_file = str( os.path.join(season['local_poster_folder'], season['local_poster']) ).replace("\\","/")
            self.RowWidgets[iwid].SeasonWidgets[season_no].ui.posterMissing.setText('<a href="file:///'+ str(poster_file) +'">Yes</a>')
            self.RowWidgets[iwid].SeasonWidgets[season_no].ui.posterMissing.setOpenExternalLinks(True)
            self.RowWidgets[iwid].SeasonWidgets[season_no].ui.posterMissingWidget.setStyleSheet(self._STYLESHEETS["missing_tab_yes"])
            cache_poster_filename = "poster_thumb_" + str(season["parentSlug"]) + "-season-" + str(season_no) + "." + str( self.fileManager.get_extension(season["local_poster"]) )
            cache_poster_location = os.path.join(self.fileManager._cache, str(season["librarySectionID"]), "images", cache_poster_filename).replace("/","\\")
            #print("Path: ", cache_poster_location)
            if os.path.isfile( cache_poster_location ):
                #print("Path is a file: ", cache_poster_location)
                pixmap = QtGui.QPixmap(f'{cache_poster_location}')
                self.RowWidgets[iwid].SeasonWidgets[season_no].ui.seasonPoster.setPixmap(pixmap)
        
        if season.get('local_background'):
            background_file = str( os.path.join(season['local_folders'][0], season['local_background']) ).replace("\\","/")
            self.RowWidgets[iwid].SeasonWidgets[season_no].ui.backgroundMissing.setText('<a href="file:///'+ background_file +'">Yes</a>')
            self.RowWidgets[iwid].SeasonWidgets[season_no].ui.backgroundMissing.setOpenExternalLinks(True)
            self.RowWidgets[iwid].SeasonWidgets[season_no].ui.backgroundMissingWidget.setStyleSheet(self._STYLESHEETS["missing_tab_yes"])
    
    def create_tv_season_widget(self, iwid, season_no, season):
        # TODO: Make TV Widget the same as Movie
        self.RowWidgets[iwid].SeasonWidgets[season_no] = QWidget()
        
        season_widget_ui = tvSeasonWidget.Ui_showSeason()
        season_widget_ui.setupUi( self.RowWidgets[iwid].SeasonWidgets[season_no] )
        
        self.RowWidgets[iwid].SeasonWidgets[season_no].ui = season_widget_ui
        # update the tv season widget
        self.update_tv_season_widget(iwid, season_no, season)
        
    def collapse_season_display(self, iwid):
        ## set the item widget maximum size to the size including button
        self.RowWidgets[iwid].setMaximumHeight(236)
        self.RowWidgets[iwid].ui.seasonListWidget.setMaximumHeight(0)
        
        ## run through and delete the season rows
        for key in list(self.RowWidgets[iwid].SeasonWidgets):
            self.RowWidgets[iwid].ui.seasonListWidgetVLayout.removeWidget(self.RowWidgets[iwid].SeasonWidgets[key])
            sip.delete(self.RowWidgets[iwid].SeasonWidgets[key])
        ## reset the movie widgets to nothing
        self.RowWidgets[iwid].SeasonWidgets = {}
        
        self.RowWidgets[iwid].season_toggle = False
        return
    
    def expand_season_display(self, seasons, iwid):
        ## make the maximum size for the widget unlimited
        self.RowWidgets[iwid].setMaximumHeight(16777215)
        self.RowWidgets[iwid].ui.seasonListWidget.setMaximumHeight(16777215)
        ## add the season widgets to the season holder
        for season_no, season in seasons.items():
            self.RowWidgets[iwid].SeasonWidgets[season_no] = {}
            self.create_tv_season_widget(iwid, season_no, season)
            self.RowWidgets[iwid].ui.seasonListWidgetVLayout.addWidget( self.RowWidgets[iwid].SeasonWidgets[season_no] )
            
        self.RowWidgets[iwid].season_toggle = True
        return
    
    def toggle_season_display(self, item, iwid):        
        season_toggle = self.RowWidgets[iwid].season_toggle
        if season_toggle == True:
            ## season display is open, so lets delete the seasons from the widget and resize to collapse
            self.RowWidgets[iwid].ui.showSeasonsButton.setIcon(self._ICONS["chevron_down"])
            self.collapse_season_display(iwid)
            self.RowWidgets[iwid].SeasonWidgets = None
            return
        else:
            self.RowWidgets[iwid].SeasonWidgets = {}
            ## season display is closed or never opened, so lets add the seasons to the display widget and resize to expand
            self.RowWidgets[iwid].ui.showSeasonsButton.setIcon(self._ICONS["chevron_up"])
            self.expand_season_display(item["seasons"], iwid)
            return
        return
    
    """ def create_tv_show_widget(self, iwid, item):
        ''' used to generate item widgets, compile the filter list and then offload the images to the image loader thread '''
        self.search_list[iwid] = []
        self.RowWidgets[iwid] = QWidget()
        widget = itemWidget.Ui_itemWidget()
        widget.setupUi(self.RowWidgets[iwid])
        self.RowWidgets[iwid].ui = widget
        self.RowWidgets[iwid].data = item
        self.search_list[iwid].append(item['title'].lower()) ## add the item to the search list
        
        ## update the widget title text
        self.update_row_widget_title_text(iwid, item['title'])
        ## update the widget title year
        self.update_row_widget_year_text(iwid, item['year'])
        ## create the empty image list for displaying images
        image_list = []
        
        ############################################
        ### update the Widget button connections ###
        ############################################        
        def download_progress_callback(progress):
            self.itemDownloadProgress[wid] = int(progress)
            
        widget.refreshButton.clicked.connect( lambda: self.refresh_widget(iwid) )
        widget.itemDataDownloadButton.clicked.connect( lambda: self.download_single_item(iwid) )
        
        ############################################
        ###  update the data inside the Widget   ###
        ############################################
        self.update_item_widget_data(iwid, item, widget)
        
        return self.RowWidgets[iwid]
    """
    
    def load_tv_show_widgets(self, library_id, filter_list=[]):
        self.library_filters = {} ## reset the library filters
        self.search_list = {} # reset the search filters
        self.current_library_id = library_id
        self.current_library_type = "show"
        #self.clear_filter_combo_items()
        if not filter_list:
            ## this is a full, unfiltered load - reset this library's filter
            ## lists so they get rebuilt fresh instead of growing every time
            self.library_filters[library_id] = {}
        self.disable_controls_during_load() ## disable the controls to prevent reloading
        
        self.switch_cache_library(self.current_library_id) ## switch the cache library
        self.clear_scroll_area()
        thread = QThread()
        worker = WidgetUpdateWorker("Load", self.fileManager)
        worker.moveToThread(thread)
        thread.started.connect(lambda: worker.run(self.current_library_id, "show", filter_list))
        #worker.finished.connect(self.calculate_filter_items) ## calculate the filter combo items once progress is complete
        worker.finished.connect(self.enable_controls_after_load) ## calculate the filter combo items once progress is complete
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        worker.progress.connect(self.update_main_progress_bar)
        worker.itemReady.connect(self.add_batch_widget_from_data)  # receives a list of 10 items to prevent refreshing too fast
        # keep this pair alive until the thread actually finishes
        pair = (thread, worker)
        self._active_threads.append(pair)
        thread.finished.connect(lambda: self._on_thread_finished(pair))
        # start thread
        thread.start()
   
    def delete_tv_show_widgets(self):
        # TODO: Make TV Widget the same as Movie
        for key in list(self.RowWidgets):
            self.mainUI.scrollAreaWidgetRowsVLayout.removeWidget(self.RowWidgets[key])
            sip.delete(self.RowWidgets[key])
        ## reset the movie widgets to nothing
        self.RowWidgets = {}
     

    ##################################################
    #######
    #######             Images
    #######
    ##################################################
   
    def update_batch_images_in_ui(self, batch_list):
        for wid, image, image_type, gen in batch_list:
            if gen != self.load_generation:
                continue  # belongs to a load that's already been replaced - discard
            if wid not in self.RowWidgets:
                continue  # widget's gone
            self.update_image_in_ui(wid, image, image_type)
    
    def update_image_in_ui(self, wid, image, image_type):
        if image_type == "poster":
            self.RowWidgets[wid].ui.itemPoster.setPixmap( QtGui.QPixmap.fromImage(image) )
        if image_type == "background":
            ## remove the old background manager filter so they dont stack up before garbage collection
            old_bg_manager = getattr(self.RowWidgets[wid], "backgroundManager", None)
            if old_bg_manager is not None:
                self.RowWidgets[wid].ui.backgroundDisplayWidget.removeEventFilter(old_bg_manager)
                old_bg_manager.deleteLater()
            self.RowWidgets[wid].backgroundManager = BackgroundScaler(self.RowWidgets[wid].ui.backgroundDisplayWidget, image, 0.30, 6) # Event Filter: Keep a reference to the 'backgroundManager' scaler filter so Python doesn't garbage collect it
        if image_type == "logo":
            ## change the movie name to the logo image
            logo = QtGui.QPixmap.fromImage(image)
            self.RowWidgets[wid].ui.itemName.setPixmap(logo)
    
    def image_loader(self, image_list):
        # Hand this batch to the one persistent image worker thread to load images
        self.loadImagesRequested.emit(image_list)
 
    def switch_cache_library(self, library_id):
        # Hand this library id to the  persistent image worker thread to switch cache folder
        self.switchCacheLibrary.emit(library_id)


    ##################################################
    #######
    #######          Library Filter
    #######
    ##################################################

    def get_filter_combo_selection(self):
        return self.mainUI.filterComboBox.currentText()
    
    def add_library_filter_item(self, filter_type, iwid):
        if not self.library_filters.get(filter_type, False):
            self.library_filters[ filter_type ] = []
        self.library_filters[ filter_type ].append(iwid)
        ## add all items to the any filter
        if not self.library_filters.get("any", False):
            self.library_filters["any"] = []
        self.library_filters["any"] = list(set(self.library_filters["any"]) | set(self.library_filters[filter_type]))

    def search_library(self):
        matches = []
        search_terms = self.mainUI.searchLineEdit.text().lower().split(" ")
        search_terms = list(filter(None, search_terms)) # remove any empty no character entries from the list
        if len(search_terms) > 0:
            for wid, titles in self.search_list.items():
                for title in titles:
                    if any( match in title for match in search_terms):
                        matches.append(wid)
            ## run through the widgets and hide any that are not in the matches
            for key, widget in self.RowWidgets.items():
                if key not in matches:
                    widget.setVisible(False)
                else:
                    widget.setVisible(True)            
            if len(matches) > 0:
                self.hide_no_items_widget()
            else:
                self.show_no_items_widget()            
        else:
            for key, widget in self.RowWidgets.items():
                widget.setVisible(True)
        
        ## force a repaint
        self.mainUI.mainScrollArea.viewport().update()
    
    def load_filtered_widgets(self):        
        combo_selection = self.get_filter_combo_selection()
        if combo_selection == "-- None --":
            for key, widget in self.RowWidgets.items():
                widget.setVisible(True)
            self.hide_no_items_widget()
        else:
            filter_type = str(combo_selection).replace("Missing ", "").lower()
            if self.library_filters.get(filter_type):
                if len(self.library_filters[filter_type]) > 0:
                    ## run through the widgets and hide any that are not in the matches
                    for key, widget in self.RowWidgets.items():
                        if key not in self.library_filters[filter_type]:
                            widget.setVisible(False)
                        else:
                            widget.setVisible(True)
                    self.hide_no_items_widget()
                else:
                    self.set_all_widget_rows_hidden()
            else:
                self.set_all_widget_rows_hidden()
        
        ## force a repaint
        self.mainUI.mainScrollArea.viewport().update()

    def create_filter_combo_box(self):
        self.mainUI.filterComboBox.addItem("-- None --")
        self.mainUI.filterComboBox.addItem("Missing Any")
        self.mainUI.filterComboBox.addItem("Missing NFO")
        self.mainUI.filterComboBox.addItem("Missing Poster")
        self.mainUI.filterComboBox.addItem("Missing Background")
        self.mainUI.filterComboBox.addItem("Missing Logo")
        self.mainUI.filterComboBox.addItem("Missing Square")
        self.mainUI.filterComboBox.activated.connect(self.load_filtered_widgets)
    
    ''' def clear_filter_combo_items(self):
        self.mainUI.filterComboBox.blockSignals(True)
        self.mainUI.filterComboBox.clear()
        self.mainUI.filterComboBox.addItem("-- None --")
        self.mainUI.filterComboBox.blockSignals(False)
        self.mainUI.filterComboBox.activated.connect(self.load_filtered_widgets)
    '''

    """ def calculate_filter_items(self):
        if self.library_filters.get(self.current_library_id, False):
            
            nfo_items = self.library_filters[self.current_library_id].get("nfo", [])
            if len(nfo_items) > 0:
                self.mainUI.filterComboBox.addItem("Missing NFO")
                
            poster_items = self.library_filters[self.current_library_id].get("poster", [])
            if len(poster_items) > 0:
                self.mainUI.filterComboBox.addItem("Missing Poster")
                
            background_items = self.library_filters[self.current_library_id].get("background", [])
            if len(background_items) > 0:
                self.mainUI.filterComboBox.addItem("Missing Background")
                
            logo_items = self.library_filters[self.current_library_id].get("logo", [])
            if len(logo_items) > 0:
                self.mainUI.filterComboBox.addItem("Missing Logo")
    """

    ''' def load_filtered_widgets(self, combo_id):
        if self.current_library_type == "movie":
            load_function = self.load_movie_widgets
        elif self.current_library_type == "show":
            load_function = self.load_tv_show_widgets
            
        ## get the filter combobox text by ID
        combo_selection = self.get_filter_combo_selection()
        if combo_selection == "-- None --":
            #print("Loading Widgets: All")
            ## none selected so load all the rows back in again
            load_function(self.current_library_id, [])
        else:
            filter_type = str(combo_selection).replace("Missing ", "").lower()
            #print("Loading Widgets: ", filter_type)
            self.clear_scroll_area()
            if self.library_filters.get(self.current_library_id, False):
                filter_items = self.library_filters[self.current_library_id].get(filter_type, [])
                #print(filter_items)
                if len(filter_items) > 0:
                    load_function(self.current_library_id, filter_items)
    '''

    def delete_layout(self, layout):
        if layout is not None and not isinstance(layout, str):
            #print(f"Deleting layout: {cur_lay.objectName()}")
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    self.delete_layout(item.layout())
            sip.delete(layout)
    
    def delete_layout_by_name(self, layout_name):
        if layout is not None and isinstance(layout_name, str):
            # Find the actual layout object within the widget
            target_layout = self.findChild(QCore.QObject, layout_name)            
            # Pass the actual layout object to the deletion function
            if target_layout is not None:
                self.delete_layout(target_layout)
    
    def closeEvent(self, event):
        ## stop the persistent image worker thread cleanly before exit,
        ## otherwise a still-running QThread at shutdown can itself trigger
        self.image_thread.quit()
        self.image_thread.wait()
        super().closeEvent(event)

## helper function not included in class to move the window centre
def move_window_center(window):
    screen = QApplication.primaryScreen()             # the screen the window will open on
    available = screen.availableGeometry()            # usable area (excludes taskbar/dock)
    frame = window.frameGeometry()                    # the window's rectangle, including the title bar
    frame.moveCenter(available.center())              # put the rectangle's centre on the screen's centre
    window.move(frame.topLeft())                      # move the window to that rectangle's top-left corner
    
app = QtWidgets.QApplication(sys.argv)
window = PlexNFOPro()
move_window_center(window)
window.show()
sys.exit(app.exec())