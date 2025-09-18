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
import time
from pprint import pprint
from typing import List, Dict, Optional
from dataclasses import dataclass
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs


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
        
    else:
        print("\n❌ No tracks could be extracted from this playlist.")
        print("\nPossible solutions:")
        print("1. Make sure the playlist is public")
        print("2. Try the Selenium method (requires Chrome browser)")
        print("3. On macOS, add the playlist to your Music library and use AppleScript method")
        print("4. Manually copy track names from the web interface")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Playlist options")
    parser.add_argument('--dont-save-tracklist', action='store_true', default=False, help="Save the extracted track data from the playlists")
    parser.add_argument('playlists', nargs='*', type=str, 
                        default=["https://music.apple.com/us/playlist/todays-hits/pl.f4d106fed2bd41149aaacabb233eb5eb"],
                        help='apple playlist urls separated by space')
    args = parser.parse_args()
    for url in args.playlists:
        get_tracklist(url, args.dont_save_tracklist)
