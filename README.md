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

Next, you'll see the scanner screen. There is a checkbox to clear the previous cache. After the first scan, if you don't check this box, only items newly added to the Plex server will be retrieved and the thumbnails generated. Speeding up the scan.

<img width="879" height="723" alt="scanner" src="https://github.com/user-attachments/assets/d5110d7f-74c6-47b2-a272-f2957733eeea" />

Two libraries that I have on my Plex Server: **"My Movies"** and **"My TV"**.

<img width="451" height="228" alt="libraries-same-as-plex" src="https://github.com/user-attachments/assets/a0f3bf5e-a42f-431f-b8b4-bcb4a4241550" />

They have now appeared on the left-hand menu in NFO Pro.

## Movie Listings:
Clicking into **"My Movies"** displays the following listing:

<img width="1149" height="962" alt="3-1-movies-library" src="https://github.com/user-attachments/assets/2607e4d4-d354-484a-a4d6-accf74508a5c" />

You will notice that there are no images for the poster and only placeholders are displayed; on the right-hand side is a box displaying what is available on the server and what is listed in the local directories. As you can see, highlighted in green, the server has *Info, Logo, Poster, Backdrop and Square art* with no *Theme Song*; locally, we have nothing.

## TV Show Listings

Clicking into **"My TV"**  displays the following listing:

<img width="1148" height="961" alt="3-2-tv-library" src="https://github.com/user-attachments/assets/406d68fa-f17b-45a2-add4-1771f3a03382" />

You can see the TV show is missing a Logo and Theme Song on the server, and also the Season 1 Backdrop.

# Downloading Movie Data

If we traverse to the Frankenstein Movie directory on our local machine, you can see there is no media stored next to the MKV video file.

<img width="1582" height="811" alt="frankenstein-folder-empty" src="https://github.com/user-attachments/assets/df20ac73-eaf9-41e5-8da5-057d020e0330" />

If we now click the download button at the end of the movie row, this will download the data for this single Movie.

<img width="899" height="271" alt="click-single-download" src="https://github.com/user-attachments/assets/42b94d0d-885a-4b27-ae78-399186d917f4" />

The program will now go and retrieve the information, compile the NFO file, download the artwork 

<img width="899" height="267" alt="frankenstein-downloaded" src="https://github.com/user-attachments/assets/08d923fd-da92-482f-8451-75307f678c42" />

Once the download has started, the progress bar will fill from top to bottom, and once completed, the artwork will be shown in the listing. 

<img width="1580" height="818" alt="4-4-frankenstein-folder-with-files" src="https://github.com/user-attachments/assets/56a0b1ab-475f-49ca-a21d-012bf5ef5db3" />

If we go back to the location of the video on our local machine, you will see that the program has placed the .nfo file and artwork in the correct location and naming conventions for Plex.

