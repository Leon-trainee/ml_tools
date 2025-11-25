import requests
import os
import re
from urllib.parse import urljoin, urlparse
import subprocess
import tempfile

def download_m3u8_video_to_mp4(m3u8_url, output_filename, headers=None):
    """
    Download m3u8 video while filtering out advertisement segments and convert to MP4.

    Args:
        m3u8_url (str): URL of the m3u8 file
        output_filename (str): Output filename for the final MP4 video
        headers (dict): Optional headers for HTTP requests
    """

    # Ensure output filename ends with .mp4
    if not output_filename.endswith('.mp4'):
        output_filename = output_filename.rsplit('.', 1)[0] + '.mp4'

    if headers is None:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    # Download and parse m3u8 content
    response = requests.get(m3u8_url, headers=headers)
    response.raise_for_status()

    m3u8_content = response.text

    # Filter out advertisement segments
    filtered_content = filter_ad_segments(m3u8_content)

    # Save filtered m3u8 content
    temp_m3u8_path = "temp_filtered.m3u8"
    with open(temp_m3u8_path, 'w', encoding='utf-8') as f:
        f.write(filtered_content)

    # Download TS segments
    base_url = m3u8_url.rsplit('/', 1)[0] + '/'
    ts_files = download_ts_segments(filtered_content, base_url, headers)

    # Create temporary TS file for conversion
    temp_ts_file = "temp_concatenated.ts"
    concatenate_videos(ts_files, temp_ts_file)

    # Convert TS to MP4 using ffmpeg
    convert_ts_to_mp4(temp_ts_file, output_filename)

    # Clean up temporary files
    cleanup_temp_files(temp_m3u8_path, ts_files)
    try:
        os.remove(temp_ts_file)
    except Exception as e:
        print(f"Error removing temporary TS file: {e}")

def convert_ts_to_mp4(input_ts_file, output_mp4_file):
    """
    Convert TS file to MP4 using ffmpeg.

    Args:
        input_ts_file (str): Input TS filename
        output_mp4_file (str): Output MP4 filename
    """
    try:
        # Use ffmpeg to convert TS to MP4
        cmd = [
            'ffmpeg',
            '-i', input_ts_file,
            '-c', 'copy',
            '-bsf:a', 'aac_adtstoasc',
            output_mp4_file
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Successfully converted to {output_mp4_file}")
        else:
            print(f"FFmpeg error: {result.stderr}")
            # Fallback: try with re-encoding
            cmd = [
                'ffmpeg',
                '-i', input_ts_file,
                '-c:v', 'libx264',
                '-c:a', 'aac',
                output_mp4_file
            ]
            subprocess.run(cmd, check=True)
            print(f"Successfully converted to {output_mp4_file} (re-encoded)")
    except FileNotFoundError:
        print("FFmpeg not found. Please install FFmpeg to convert TS to MP4.")
        print("You can install it with: conda install ffmpeg or download from https://ffmpeg.org/")
    except subprocess.CalledProcessError as e:
        print(f"Error converting TS to MP4: {e}")

# The rest of the functions remain the same as in your existing code
# filter_ad_segments, download_ts_segments, concatenate_videos, cleanup_temp_files
def filter_ad_segments(m3u8_content):
    """
    Filter out advertisement segments based on EXT-X-DISCONTINUITY tags.

    Rules:
    - Keep content after first #EXT-X-DISCONTINUITY
    - Remove segments between 2nd and 3rd #EXT-X-DISCONTINUITY tags
    - Continue pattern: remove segments between 4th-5th, 6th-7th, etc.

    Args:
        m3u8_content (str): Raw m3u8 file content

    Returns:
        str: Filtered m3u8 content without advertisement segments
    """
    lines = m3u8_content.strip().split('\n')
    filtered_lines = []

    discontinuity_count = 0
    skip_segment = False

    for line in lines:
        if line.startswith('#EXT-X-DISCONTINUITY'):
            discontinuity_count += 1

            # First discontinuity: keep content after it
            if discontinuity_count == 1:
                filtered_lines.append(line)
                skip_segment = False
            # Even numbered discontinuities (2, 4, 6...): start skipping
            elif discontinuity_count % 2 == 0:
                skip_segment = True
            # Odd numbered discontinuities (3, 5, 7...): stop skipping
            else:
                skip_segment = False
                filtered_lines.append(line)
        elif not skip_segment:
            filtered_lines.append(line)

    return '\n'.join(filtered_lines)

def filter_ad_segments(m3u8_content):
    """
    Filter out advertisement segments based on EXT-X-DISCONTINUITY tags.

    Args:
        m3u8_content (str): Raw m3u8 file content

    Returns:
        str: Filtered m3u8 content without advertisement segments
    """
    lines = m3u8_content.strip().split('\n')
    filtered_lines = []

    discontinuity_count = 0
    skip_segment = False

    for line in lines:
        if line.startswith('#EXT-X-DISCONTINUITY'):
            discontinuity_count += 1

            # First discontinuity: keep content after it
            if discontinuity_count == 1:
                filtered_lines.append(line)
                skip_segment = False
            # Even numbered discontinuities (2, 4, 6...): start skipping
            elif discontinuity_count % 2 == 0:
                skip_segment = True
            # Odd numbered discontinuities (3, 5, 7...): stop skipping
            else:
                skip_segment = False
                filtered_lines.append(line)
        elif not skip_segment:
            filtered_lines.append(line)

    return '\n'.join(filtered_lines)

def download_ts_segments(m3u8_content, base_url, headers):
    """
    Download TS segments from filtered m3u8 content.

    Args:
        m3u8_content (str): Filtered m3u8 content
        base_url (str): Base URL for resolving relative paths
        headers (dict): Headers for HTTP requests

    Returns:
        list: List of downloaded TS filenames
    """
    lines = m3u8_content.strip().split('\n')
    ts_files = []

    for line in lines:
        if line.endswith('.ts') or '.ts?' in line:
            ts_url = urljoin(base_url, line)
            filename = os.path.basename(urlparse(ts_url).path)

            if not filename:
                filename = f"segment_{len(ts_files)}.ts"

            print(f"Downloading {filename}...")
            response = requests.get(ts_url, headers=headers)
            response.raise_for_status()

            with open(filename, 'wb') as f:
                f.write(response.content)

            ts_files.append(filename)

    return ts_files

def concatenate_videos(ts_files, output_filename):
    """
    Concatenate TS files into a single video file.

    Args:
        ts_files (list): List of TS filenames
        output_filename (str): Output filename
    """
    print("Concatenating video segments...")

    with open(output_filename, 'wb') as outfile:
        for ts_file in ts_files:
            with open(ts_file, 'rb') as infile:
                outfile.write(infile.read())

def cleanup_temp_files(temp_m3u8_path, ts_files):
    """
    Clean up temporary files.

    Args:
        temp_m3u8_path (str): Path to temporary m3u8 file
        ts_files (list): List of TS filenames to delete
    """
    try:
        os.remove(temp_m3u8_path)
        for ts_file in ts_files:
            os.remove(ts_file)
        print("Temporary files cleaned up.")
    except Exception as e:
        print(f"Error cleaning up temporary files: {e}")

import json
import hashlib

def get_download_state_filename(m3u8_url):
    """Generate a unique state filename based on m3u8 URL"""
    url_hash = hashlib.md5(m3u8_url.encode()).hexdigest()
    return f"download_state_{url_hash}.json"

def load_download_state(m3u8_url):
    """Load download state from file"""
    state_file = get_download_state_filename(m3u8_url)
    try:
        with open(state_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"downloaded_segments": [], "total_segments": 0}

def save_download_state(m3u8_url, state):
    """Save download state to file"""
    state_file = get_download_state_filename(m3u8_url)
    with open(state_file, 'w') as f:
        json.dump(state, f)

def download_m3u8_video_to_mp4_with_resume(m3u8_url, output_filename, headers=None):
    """
    Enhanced version with resume capability
    """
    # Ensure output filename ends with .mp4
    if not output_filename.endswith('.mp4'):
        output_filename = output_filename.rsplit('.', 1)[0] + '.mp4'

    if headers is None:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    # Load download state
    download_state = load_download_state(m3u8_url)
    downloaded_segments = set(download_state.get("downloaded_segments", []))

    # Download and parse m3u8 content
    response = requests.get(m3u8_url, headers=headers)
    response.raise_for_status()

    m3u8_content = response.text

    # Filter out advertisement segments
    filtered_content = filter_ad_segments(m3u8_content)

    # Save filtered m3u8 content
    temp_m3u8_path = "temp_filtered.m3u8"
    with open(temp_m3u8_path, 'w', encoding='utf-8') as f:
        f.write(filtered_content)

    # Download TS segments with resume support
    base_url = m3u8_url.rsplit('/', 1)[0] + '/'
    ts_files = download_ts_segments_with_resume(
        filtered_content, base_url, headers, downloaded_segments, m3u8_url
    )

    # Create temporary TS file for conversion
    temp_ts_file = "temp_concatenated.ts"
    concatenate_videos(ts_files, temp_ts_file)

    # Convert TS to MP4 using ffmpeg
    convert_ts_to_mp4(temp_ts_file, output_filename)

    # Clean up temporary files
    cleanup_temp_files(temp_m3u8_path, ts_files)
    try:
        os.remove(temp_ts_file)
        # Remove state file after successful download
        state_file = get_download_state_filename(m3u8_url)
        if os.path.exists(state_file):
            os.remove(state_file)
    except Exception as e:
        print(f"Error removing temporary files: {e}")

def download_ts_segments_with_resume(m3u8_content, base_url, headers, downloaded_segments, m3u8_url):
    """
    Download TS segments with resume support
    """
    lines = m3u8_content.strip().split('\n')
    ts_files = []

    # Load current state
    download_state = load_download_state(m3u8_url)
    downloaded_list = download_state.get("downloaded_segments", [])

    # Count total segments
    total_segments = sum(1 for line in lines if line.endswith('.ts') or '.ts?' in line)
    download_state["total_segments"] = total_segments
    save_download_state(m3u8_url, download_state)

    segment_index = 0
    for line in lines:
        if line.endswith('.ts') or '.ts?' in line:
            segment_index += 1

            ts_url = urljoin(base_url, line)
            filename = os.path.basename(urlparse(ts_url).path)

            if not filename:
                filename = f"segment_{len(ts_files)}.ts"

            # Check if segment was already downloaded
            if filename in downloaded_segments:
                print(f"Skipping {filename} (already downloaded)")
                ts_files.append(filename)
                continue

            print(f"Downloading {filename} ({segment_index}/{total_segments})...")
            try:
                response = requests.get(ts_url, headers=headers)
                response.raise_for_status()

                with open(filename, 'wb') as f:
                    f.write(response.content)

                ts_files.append(filename)

                # Update state
                if filename not in downloaded_list:
                    downloaded_list.append(filename)
                download_state["downloaded_segments"] = downloaded_list
                save_download_state(m3u8_url, download_state)

            except Exception as e:
                print(f"Error downloading {filename}: {e}")
                raise

    return ts_files

if __name__ == '__main__':
    m3u8_url = 'https://vip.dytt-cinema.com/20251121/41158_e3f37a80/3000k/hls/mixed.m3u8'
    download_m3u8_video_to_mp4_with_resume(m3u8_url, 'D:/video/浪荡山小妖怪.mp4')
