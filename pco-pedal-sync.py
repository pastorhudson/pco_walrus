#!/usr/bin/env python3
"""
PCO to Pedal Project Sync

This script updates a pedal project file with songs from Planning Center Online services.
It fetches all songs from PCO and updates the pedal project with matching song titles, BPM, and time signatures.

Requirements:
- pypco library (install with: pip install pypco)
- Planning Center Online API credentials in config.ini
"""

import json
import os
import argparse
import sys
import configparser
from pypco import PCO

# Define CLI arguments
parser = argparse.ArgumentParser(description='Sync Planning Center songs with Pedal Project')
parser.add_argument('--pedal-file', type=str, required=True, help='Path to the pedal project JSON file')
parser.add_argument('--output-file', type=str, help='Path to save the updated pedal project file')
parser.add_argument('--config', type=str, default='config.ini',
                    help='Path to config file with PCO credentials (default: config.ini)')
parser.add_argument('--max-songs', type=int, default=128,
                    help='Maximum number of songs to fetch from PCO (default: 128)')
args = parser.parse_args()


def load_config(config_path):
    """Load PCO credentials from config file."""
    if not os.path.exists(config_path):
        print(f"Error: Config file '{config_path}' not found.")
        print("Please create a config.ini file with your PCO credentials.")
        print("Example config.ini:")
        print("[pco]")
        print("app_id = YOUR_PCO_APP_ID")
        print("secret = YOUR_PCO_SECRET")
        sys.exit(1)

    config = configparser.ConfigParser()
    config.read(config_path)

    if 'pco' not in config:
        print("Error: 'pco' section not found in config file.")
        sys.exit(1)

    if 'app_id' not in config['pco'] or 'secret' not in config['pco']:
        print("Error: 'app_id' or 'secret' not found in 'pco' section of config file.")
        sys.exit(1)

    return config['pco']['app_id'], config['pco']['secret']


def load_pedal_project(file_path):
    """Load the pedal project file."""
    with open(file_path, 'r') as f:
        return json.load(f)


def save_pedal_project(project, file_path):
    """Save the pedal project file."""
    with open(file_path, 'w') as f:
        json.dump(project, f)
    print(f"Updated pedal project saved to {file_path}")


def convert_time_signature(time_signature_string):
    """Convert PCO time signature string to pedal project format."""
    if not time_signature_string:
        return 3  # Default to 3 (4/4 time)

    # Handle common time signatures
    if time_signature_string == "2/4":
        return 1
    elif time_signature_string == "3/4":
        return 2
    elif time_signature_string == "4/4":
        return 3
    elif time_signature_string == "6/8":
        return 4

    # For other time signatures, just use the first number
    try:
        numerator = int(time_signature_string.split('/')[0])
        if numerator == 4:
            return 3  # 4/4 time
        elif numerator == 3:
            return 2  # 3/4 time
        elif numerator == 6:
            return 1  # 6/8 time
        else:
            return 3  # Default to 4/4 time
    except:
        return 3  # Default to 4/4 time


def main():
    # Load PCO credentials from config file
    try:
        pco_app_id, pco_secret = load_config(args.config)
        print(f"Loaded PCO credentials from {args.config}")
    except Exception as e:
        print(f"Error loading config: {str(e)}")
        sys.exit(1)

    # Load the pedal project file
    try:
        pedal_project = load_pedal_project(args.pedal_file)
        print(f"Loaded pedal project from {args.pedal_file}")
    except Exception as e:
        print(f"Error loading pedal project file: {str(e)}")
        sys.exit(1)

    try:
        # Initialize PCO API client
        pco = PCO(pco_app_id, pco_secret)

        # Create a dictionary to store PCO songs info
        pco_songs = {}

        # Get all songs directly using iterate method
        print(f"Fetching songs from Planning Center Online...")
        song_count = 0

        # Use pco.iterate to get all songs - it handles pagination automatically
        for song in pco.iterate('/services/v2/songs', params={'per_page': 100}):
            # Stop if we've reached the maximum number of songs
            if song_count >= args.max_songs:
                print(f"Reached maximum song limit ({args.max_songs}).")
                break

            # Extract song ID and title correctly
            song_id = song['data']['id']
            song_title = song['data']['attributes'].get('title', 'Unknown Song')

            # If song already exists in our dictionary, skip
            if song_title in pco_songs:
                continue

            song_count += 1
            print(f"Processing song [{song_count}]: {song_title} (ID: {song_id})")

            # Set default values
            bpm = 80  # Default BPM
            time_sig = 3  # Default time signature (4/4)

            # Get arrangements for this song from the correct endpoint
            try:
                arrangement_response = pco.get(f'/services/v2/songs/{song_id}/arrangements')

                if 'data' in arrangement_response and arrangement_response['data']:
                    arrangements = arrangement_response['data']

                    if arrangements:
                        # Use the first arrangement
                        arr = arrangements[0]

                        if 'attributes' in arr and 'bpm' in arr['attributes'] and arr['attributes']['bpm']:
                            try:
                                bpm_value = arr['attributes']['bpm']
                                if bpm_value and bpm_value != "":
                                    bpm = float(bpm_value)
                            except (ValueError, TypeError):
                                print(
                                    f"  Warning: Could not convert BPM value '{bpm_value}' to number for song {song_title}")

                        if 'attributes' in arr and 'time_signature' in arr['attributes'] and arr['attributes'][
                            'time_signature']:
                            time_sig = convert_time_signature(arr['attributes']['time_signature'])
            except Exception as arr_err:
                print(f"  Warning: Could not fetch arrangements for {song_title}: {str(arr_err)}")

            # Store the song info
            pco_songs[song_title] = {
                'title': song_title,
                'bpm': bpm,
                'metro_time_sig': time_sig
            }
            print(f"  Found: {song_title} (BPM: {bpm}, Time Sig: {time_sig})")

        print(f"Fetched {len(pco_songs)} songs from Planning Center Online.")

        # Update pedal project songs
        updated_count = 0
        pco_songs_added = []

        # First pass: update existing songs
        for i, song in enumerate(pedal_project['songs']):
            if song['name'] in pco_songs:
                pco_song = pco_songs[song['name']]
                pedal_project['songs'][i]['bpm'] = pco_song['bpm']
                pedal_project['songs'][i]['metro_time_sig'] = pco_song['metro_time_sig']
                updated_count += 1
                pco_songs_added.append(song['name'])
                print(f"Updated song: {song['name']} (BPM: {pco_song['bpm']}, Time Sig: {pco_song['metro_time_sig']})")

        # Second pass: add new songs to empty slots
        for i, song in enumerate(pedal_project['songs']):
            # If this is a default/empty song slot and we have more PCO songs to add
            if (song['name'].startswith('Song ') or song['name'] == '') and pco_songs_added != list(pco_songs.keys()):
                # Find a PCO song that hasn't been added yet
                for pco_song_title, pco_song in pco_songs.items():
                    if pco_song_title not in pco_songs_added:
                        pedal_project['songs'][i]['name'] = pco_song_title
                        pedal_project['songs'][i]['bpm'] = pco_song['bpm']
                        pedal_project['songs'][i]['metro_time_sig'] = pco_song['metro_time_sig']
                        updated_count += 1
                        pco_songs_added.append(pco_song_title)
                        print(
                            f"Added new song: {pco_song_title} (BPM: {pco_song['bpm']}, Time Sig: {pco_song['metro_time_sig']})")
                        break

        # Save the updated pedal project
        output_file = args.output_file if args.output_file else args.pedal_file
        save_pedal_project(pedal_project, output_file)

        print(f"Sync complete! Updated {updated_count} songs.")

        # List PCO songs that weren't added (if any)
        songs_not_added = [title for title in pco_songs.keys() if title not in pco_songs_added]
        if songs_not_added:
            not_added_count = len(songs_not_added)
            print(f"\n{not_added_count} PCO songs weren't added (no more slots available). First 10:")
            for song in songs_not_added[:10]:
                print(f"- {song}")
            if not_added_count > 10:
                print(f"... and {not_added_count - 10} more")

    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        if "401" in str(e):
            print("Authentication failed. Please check your PCO credentials in the config file.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()