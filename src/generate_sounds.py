import subprocess
import os

def gen_sound(filename, freq_pattern, duration=0.5):
    """Generate a wav file using ffmpeg sine filters."""
    # freq_pattern is like "440, 880" for two notes
    # For simplicity, we'll just do a single or double beep
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi",
        f"-i", f"sine=frequency={freq_pattern}:duration={duration}",
        "-ar", "48000", "-ac", "2", filename
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def main():
    print("Generating system sounds...")
    # Startup: Ascending triple chime
    # We'll use a more complex filter for a 'chime' feel if possible, 
    # but simple sine beeps are safest for now.
    gen_sound("chime_startup.wav", "660", 0.1) 
    # Update OK: Double high beep
    gen_sound("chime_update_ok.wav", "880", 0.3)
    # Update Err: Low buzz
    gen_sound("chime_update_err.wav", "220", 0.5)
    print("Done.")

if __name__ == "__main__":
    main()
