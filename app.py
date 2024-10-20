import streamlit as st
import moviepy.editor as mp
import whisper
import os
import pyttsx3
from pydub import AudioSegment  # Make sure to install pydub
import requests
import json

# Azure GPT-4o settings
AZURE_ENDPOINT = "https://internshala.openai.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2024-08-01-preview"
AZURE_API_KEY = "22ec84421ec24230a3638d1b51e3a7dc"

# Initialize the TTS engine
engine = pyttsx3.init()

# Function to transcribe audio using Whisper with word-level timestamps
def transcribe_audio_with_timestamps(audio_path):
    model = whisper.load_model("base")
    result = model.transcribe(audio_path, word_timestamps=True)
    return result["segments"]  # Returns segments containing text and timestamps

def correct_transcription(text):
    headers = {
        "Content-Type": "application/json",
        "api-key": AZURE_API_KEY
    }
    data = {
        "messages": [
            {
                "role": "system",
                "content": "You are an assistant that corrects transcriptions. Please remove any filler words like 'um', 'hmm', and fix grammatical errors."
            },
            {
                "role": "user",
                "content": text
            }
        ]
    }

    # Send request to Azure GPT-4o API
    response = requests.post(AZURE_ENDPOINT, headers=headers, json=data)
    
    # Check if the request was successful
    if response.status_code != 200:
        st.error(f"API request failed with status code {response.status_code}")
        return ""
    
    # Get the response as JSON
    response_json = response.json()

    # Debugging: Print the full response
  

    # Handle case where 'choices' key is missing
    try:
        corrected_text = response_json["choices"][0]["message"]["content"]
    except KeyError:
        st.error("Unexpected response format. 'choices' key not found.")
        corrected_text = ""
    
    return corrected_text


# Function to synthesize speech with pauses based on gaps between words
def synthesize_speech(text, output_audio_path):
    # Split corrected text into words
    words = text.split()
    audio_segments = []
    
    for i in range(len(words)):
        word = words[i]

        # Use pyttsx3 to generate speech for the word
        engine.save_to_file(word, 'temp_word.mp3')
        engine.runAndWait()
        word_audio = AudioSegment.from_file('temp_word.mp3')
        
        # Add the word audio to the segments
        audio_segments.append(word_audio)

        # Add pauses between words (200ms pause between words as default)
        if i < len(words) - 1:
            silence = AudioSegment.silent(duration=200)
            audio_segments.append(silence)

    # Combine all audio segments into a single audio file
    combined_audio = sum(audio_segments)

    # Export the final combined audio to a file
    combined_audio.export(output_audio_path, format="wav")
    return combined_audio.duration_seconds  # Return the total duration of the synthesized audio

# Function to replace audio in video
def replace_audio_in_video(video_path, new_audio_path, output_video_path):
    video = mp.VideoFileClip(video_path)
    new_audio = mp.AudioFileClip(new_audio_path)
    
    video_with_new_audio = video.set_audio(new_audio)
    video_with_new_audio.write_videofile(output_video_path, codec="libx264", audio_codec='aac')

# Streamlit app
def main():
    st.title("Project")
    
    # Step 1: Upload video
    video_file = st.file_uploader("Upload your video", type=["mp4", "mov", "avi"])
    
    if video_file:
        video_path = os.path.join("temp_video.mp4")
        
        # Save the uploaded video to a temporary file
        with open(video_path, "wb") as f:
            f.write(video_file.read())
        
        st.video(video_path)
        
        # Step 2: Extract audio from video
        video = mp.VideoFileClip(video_path)
        audio_path = "extracted_audio.wav"
        video.audio.write_audiofile(audio_path)
        st.success("Audio extracted from the video!")

        # Step 3: Transcribe audio with timestamps using Whisper
        segments = transcribe_audio_with_timestamps(audio_path)
        transcription_text = " ".join([word_info["word"] for segment in segments for word_info in segment["words"]])
        
        # Step 4: Send the transcription to Azure GPT-4o for correction
        corrected_transcription = correct_transcription(transcription_text)
        st.subheader("Corrected Transcription:")
        st.write(corrected_transcription)

        # Step 5: Synthesize corrected transcription with pauses
        output_audio_path = "new_audio.wav"
        synthesized_audio_duration = synthesize_speech(corrected_transcription, output_audio_path)
        st.success("New audio generated ")

        # Add silence before the first word based on Whisper's first word timestamp
        total_duration = segments[0]["words"][0]["start"] * 1000  # Convert to milliseconds
        silence = AudioSegment.silent(duration=total_duration)

        # Combine silence with the new audio
        new_audio = AudioSegment.from_wav(output_audio_path)
        final_audio = silence + new_audio

        # Save the adjusted audio
        adjusted_audio_path = "adjusted_new_audio.wav"
        final_audio.export(adjusted_audio_path, format="wav")

        # Replace original video audio with the adjusted new audio
        output_video_path = "final_video_with_new_audio.mp4"
        replace_audio_in_video(video_path, adjusted_audio_path, output_video_path)
        st.success("Video with replaced audio generated successfully!")
        
        # Display the video with the new audio
        st.video(output_video_path)

if __name__ == "__main__":
    main()
