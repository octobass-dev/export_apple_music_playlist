#!/usr/bin/env python3
"""
Apple Music Playlist Track Extractor

Multiple methods to extract track information from Apple Music playlist URLs.
Since Apple Music doesn't have a public API, these methods use various workarounds.

Required libraries:
pip install requests beautifulsoup4 selenium webdriver-manager lxml pyobjc-framework-ScriptingBridge
"""

import argparse
import json
import re
import os
import time
from pprint import pprint
from typing import List, Dict, Optional
from dataclasses import dataclass
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
import yt_dlp
from fuzzywuzzy import fuzz

DEBUG=False

@dataclass
class Track:
    """Represents a track with metadata"""
    title: str
    artist: str
    album: str = ""
    duration: int = 0
    track_number: int = 0
    album_art_url: str = ""
    url: str = ""

class AppleMusicExtractor:
    """Extract tracks from Apple Music playlists using various methods"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def extract_playlist_id(self, url: str) -> Optional[str]:
        """Extract playlist ID from Apple Music URL"""
        # Apple Music playlist URLs typically look like:
        # https://music.apple.com/us/playlist/playlist-name/pl.u-abc123
        # https://music.apple.com/us/playlist/playlist-name/pl.abc123
        
        patterns = [
            r'/playlist/[^/]+/(pl\.[a-zA-Z0-9_-]+)',
            r'playlist/(pl\.[a-zA-Z0-9_-]+)',
            r'playlist/([a-zA-Z0-9._-]+)$'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                print(match.group(1))
                return match.group(1)
        
        return None
    
    def method1_web_scraping(self, playlist_url: str) -> List[Track]:
        """
        Method 1: Basic web scraping (limited effectiveness)
        Apple Music's web interface is heavily JavaScript-based, so this has limited success
        """
        print("Method 1: Attempting basic web scraping...")
        
        try:
            if not DEBUG: 
                response = self.session.get(playlist_url)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')
            else: 
                with open("./output.html", "r", encoding="utf-8") as file:
                    html_content = file.read()
                soup = BeautifulSoup(html_content, 'html.parser')

            
            tracks = []
            
            # Look for JSON-LD structured data
            scripts = soup.find_all('script', type='application/json')
            for i, script in enumerate(scripts):
                try:
                    data = json.loads(script.string)[0]
                    #with open(f'./playlist_{i}.json', 'w') as f:
                    #    f.write(json.dumps(data, indent=4))
                    for td in data['data']['sections']:
                        if td['itemKind'] == 'trackLockup':
                            print(td.keys())
                            for track_data in td['items']:
                                print(track_data.keys())
                                track = Track(
                                    title=track_data.get('title', ''),
                                    artist=track_data.get('artistName', ''),
                                    duration=track_data.get('duration',0),
                                    url=track_data["contentDescriptor"]["url"]
                                )
                                tracks.append(track)
                except json.JSONDecodeError:
                    continue
            
            # Look for meta tags
            if not tracks:
                title_meta = soup.find('meta', property='og:title')
                if title_meta:
                    print(f"Found playlist: {title_meta.get('content')}")
            
            return tracks
            
        except Exception as e:
            print(f"Method 1 failed: {e}")
            return []
    
    def extract_tracks(self, playlist_url: str, methods: List[str] = None) -> List[Track]:
        """
        Extract tracks using multiple methods
        
        Args:
            playlist_url: Apple Music playlist URL
        
        Returns:
            List of Track objects
        """
        if methods is None:
            methods = ['scraping']
        
        all_tracks = []
        
        print(f"Extracting tracks from: {playlist_url}")
        print("=" * 60)
        
        for method in methods:
            tracks = []
            
            if method == 'scraping':
                tracks = self.method1_web_scraping(playlist_url)
            else:
                print(f"Method {method} not implemented yet")

            if tracks:
                print(f"✓ {method.title()} method found {len(tracks)} tracks")
                all_tracks.extend(tracks)
                break
            else:
                print(f"✗ {method.title()} method found no tracks")
        
        # Remove duplicates
        unique_tracks = []
        seen = set()
        
        for track in all_tracks:
            key = (track.title.lower(), track.artist.lower())
            if key not in seen:
                seen.add(key)
                unique_tracks.append(track)
        
        print(f"\nTotal unique tracks found: {len(unique_tracks)}")
        return unique_tracks

def get_tracklist(playlist_url, dont_save):
    """Example usage"""
    extractor = AppleMusicExtractor()
    
    # Try all available methods
    tag = playlist_url.split('?', 1)[0].split('/')[-1]
    tracks = extractor.extract_tracks(playlist_url)
    
    if tracks:
        print("\n" + "=" * 60)
        print("EXTRACTED TRACKS:")
        print("=" * 60)
        
        for i, track in enumerate(tracks, 1):
            print(f"{i:2d}. {track.artist} - {track.title}")
            if track.album:
                print(f"     Album: {track.album}")
        
        # Save to JSON
        tracks_data = {
            "playlist_url": playlist_url,
            "total_tracks": len(tracks),
            "songs": [
                {
                    "title": track.title,
                    "artist": track.artist,
                    "album": track.album,
                    "duration": track.duration
                }
                for track in tracks
            ]
        }

        if not dont_save:
            fname = f"tracks_{tag}.json" 
            with open(fname, "w") as f:
                json.dump(tracks_data, f, indent=2)
            
            print(f"\nTracks saved to: {fname}")
        return tracks_data
        
    else:
        print("\n❌ No tracks could be extracted from this playlist.")
        print("\nPossible solutions:")
        print("1. Make sure the playlist is public")
        print("2. Try the Selenium method (requires Chrome browser)")
        print("3. On macOS, add the playlist to your Music library and use AppleScript method")
        print("4. Manually copy track names from the web interface")


class YTD:
    def __init__(self, download_path: str = "./downloads"):
        """Initialize the song downloader with specified download path."""
        self.download_path = download_path
        os.makedirs(download_path, exist_ok=True)
        
        # Configure yt-dlp options for audio download
        self.ydl_opts = {
            'download_archive': f'{download_path}/downloaded.txt',
            'format': 'bestaudio/best',
            'outtmpl': f'{download_path}/%(title)s.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': False,
            'no_warnings': False,
        }
    
    def search_song(self, song_name: str, artist: str, max_results: int = 10) -> list:
        """
        Search for a song on YouTube and return search results.
        
        Args:
            song_name: Name of the song
            artist: Artist name
            max_results: Maximum number of search results to return
            
        Returns:
            List of dictionaries containing video information
        """
        search_query = f"{artist} {song_name}"
        
        search_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }
        
        with yt_dlp.YoutubeDL(search_opts) as ydl:
            try:
                # Search YouTube
                search_results = ydl.extract_info(
                    f"ytsearch{max_results}:{search_query}",
                    download=False
                )
                
                if 'entries' in search_results:
                    return search_results['entries']
                else:
                    return []
                    
            except Exception as e:
                print(f"Error searching for song: {e}")
                return []

    # Match name, artist, duration
    def calculate_confidence(self, original, result: dict) -> float:
        """Calculate confidence score for a match"""
        result_title = result.get('title', '').lower()
        # Remove keywords - 
        keywords = ['(', ')', '[', ']', 'hd', 'original', 'lyrics', 'video', 'lyrics', 'official']
        for w in keywords:
            result_title = result_title.replace(w, '')
        result_title = result_title.strip()
        print(result_title)
        result_artists = [artist['name'].lower() for artist in result.get('artists', [])]
        result_artist = ', '.join(result_artists)
        
        original_title = original['title'].lower()
        original_artist = original['artist'].lower()
        
        # Title similarity
        title_score = fuzz.ratio(original_title, result_title) / 100
        
        # Artist similarity (check against all artists)
        artist_scores = [fuzz.ratio(original_artist, artist) for artist in result_artists]
        artist_score = max(artist_scores) / 100 if artist_scores else 0

        # Duration gap seconds?
        dur_diff = abs(original['duration'] - result['duration'])

        # Overall confidence (weighted average)
        confidence = (title_score * 0.4 + artist_score * 0.6 - dur_diff * 0.0002)
        return confidence

def get_tracks_on_yt(tracks, thresh = 0.2):
    ytd = YTD()
    # Loop over tracks, search, 
    for track in tracks:
        track['duration'] = track['duration']/1000.0
        print(track)
        res = ytd.search_song(track['title'], track['artist'])
        best_conf = thresh
        best_match = None
        for r in res:
            # Fuzzy match title, approx duration
            confidence = ytd.calculate_confidence(track, r)
            print(r['title'], r['duration'], confidence)
            if best_conf < confidence:
                best_match = r
                best_conf = confidence

        # download track
        if best_match is not None:
            print(f"Best match: {best_match['title']}")
            print(f"URL: https://youtube.com/watch?v={best_match['id']}")
            # Download the song
            video_url = f"https://youtube.com/watch?v={best_match['id']}"
            with yt_dlp.YoutubeDL(ytd.ydl_opts) as ydl:
                ydl.download([video_url])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Playlist options")
    parser.add_argument('--dont-save-tracklist', action='store_true', default=False, help="Save the extracted track data from the playlists")
    parser.add_argument('playlists', nargs='*', type=str, 
                        default=["https://music.apple.com/us/playlist/todays-hits/pl.f4d106fed2bd41149aaacabb233eb5eb"],
                        help='apple playlist urls separated by space')
    args = parser.parse_args()
    for url in args.playlists:
        tracks = get_tracklist(url, args.dont_save_tracklist)
        # TODO : Read tracks from json file - modularity
        
    #with open('./tracks_pl.u-06oxp9gFYbm1vzN.json', 'r') as f:
    #    tracks = json.loads(f.read())
    get_tracks_on_yt(tracks['songs'])
