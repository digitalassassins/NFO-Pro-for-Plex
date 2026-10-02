# NFO Pro for Plex
Plex backup software, built in our spare time. It pulls all metadata fields into .nfo files. It downloads all artwork, including poster, background, logo, square, season artwork & theme song, alongside your media with a single click.

## How to use:

Download the latest portable version for Windows here: https://github.com/digitalassassins/NFO-Pro-for-Plex/releases; 
Alternatively, download the source code and run it from within a Python Virtual Environment.

## Build from Source
If you would like, you can also build from source using the "-BUILD.bat" file on Windows to build a .exe or "-BUILD.sh" on Linux to build an executable ELF file

## First Launch
When you first launch the application, you will be presented with a blank page. You will want to set up initial settings; in the bottom left-hand corner of the window, click "Settings".
<img width="1149" height="962" alt="on-first-open-click-settings" src="https://github.com/user-attachments/assets/113f9102-90c2-45d1-b958-92b4b94e389f" />

You will then be presented with the settings page. First, enter your Plex server URL and Token into the "Server Settings" box.
<img width="1122" height="781" alt="1-2-settings" src="https://github.com/user-attachments/assets/34ecf692-72a3-4b28-8a56-b2efc76174e9" />

You will also want to choose what is important to download for your library from the options: NFO (Being the main Movie or Show NFO), Poster, Logo, Background, Square, Season NFO, Season Poster, Season Backdrop, Episode NFO, Episode Thumbnail, and Theme Song. The checkbox to the right is for when you want to overwrite your currently existing local files with what exists on the Plex Server. If overwrite is not checked, only the missing files will be added to your local library, and nothing existing will be overwritten.

**Save Actors in NFO**: This is optional. If actors are saved into local NFO files, Plex will not use the built-in Plex Filmography features, as it can not match the Actor to the Plex Actor listing. 
Leaving this off is useful if you have the Plex Metadata Agent scanner as the fallback to NFO. The NFO Metadata Agent will fill in all the film data from your NFO files; then the Plex Metadata Agent will source and match the actor listings.

### Adding Folders
You will notice on the settings page two sections, one "TV Folders" and another "Movies Folders". This is used to match your local folders to Plex's Library folders.
For instance, we have a Library on our Synology NAS which has a Unix folder structure listed as "/volumeUSB1/usbshare1-2/Tutorials" locally on the NAS drive.
We have mounted that same library on our Windows machine, and it is listed as "X:\NASDrive\Tutorials".
When we add a folder here, during a scan, the scanner will match folder structures to match and map Server directories to Local Directories.
e.g. if we have a Video file located at:

**NAS:** "/volumeUSB1/usbshare1-2/Tutorials/How to Tie a Windsor Knot/How-to-Tie-a-Windsor-Knot-1080p-hevc.mkv"
**Windows:** "X:\NASDrive\Tutorials\How to Tie a Windsor Knot\How-to-Tie-a-Windsor-Knot-1080p-hevc.mkv"

The program will detect the server directory as "/volumeUSB1/usbshare1-2/Tutorials/How to Tie a Windsor Knot/"
and the local directory will be: "X:\NASDrive\Tutorials\How to Tie a Windsor Knot\", which will then be used to save files locally.
Ensure you add all folders for your libraries listed in Plex; if not, those titles will be skipped entirely and will not be added to the Library listings.

## Running a Scan
Once you have set up Plex settings and added your library, the next step is to do a server scan to map paths and create thumbnails for your library. Click "Scan" in the bottom left corner to start a scan.
<img width="1149" height="962" alt="first-open-scan" src="https://github.com/user-attachments/assets/bf291520-733f-4601-8bff-8ad174774669" />

Next, you will be presented with the scanner screen. There is a checkbox to clear the previous cache. After the first scan, if you don't check this box, only items newly added to the Plex server will be retrieved and the thumbnails generated. Speeding up future scans.
<img width="879" height="723" alt="scanner" src="https://github.com/user-attachments/assets/d5110d7f-74c6-47b2-a272-f2957733eeea" />


