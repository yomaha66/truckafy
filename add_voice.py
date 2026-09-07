"""Add a shared-library voice to My Voices and render the full mix with it. Usage: python3 add_voice.py N [label]"""
import sys, json, os, urllib.request, eleven, main
n = int(sys.argv[1]); label = sys.argv[2] if len(sys.argv) > 2 else "lib%d" % n
v = json.load(open("library.json"))[n - 1]
req = urllib.request.Request("https://api.elevenlabs.io/v1/voices/add/%s/%s" % (v["public_owner_id"], v["voice_id"]),
    data=json.dumps({"new_name": "TRUCKAFY " + label}).encode(), method="POST",
    headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": "application/json"})
try:
    vid = json.load(urllib.request.urlopen(req))["voice_id"]
except urllib.error.HTTPError as e:
    body = e.read().decode()
    if "already" in body.lower():
        vid = v["voice_id"]
    else:
        raise SystemExit("add failed: %s %s" % (e.code, body[:300]))
print("voice", v["name"], "->", vid)
DEMO = "Sunday, Sunday, Sunday! Hey Julie, can you grab dog food for Jasper on the way home? We are almost out."
pcm = "/tmp/%s.pcm" % label
open(pcm, "wb").write(eleven.tts_pcm24k(DEMO, vid))
os.environ["PITCH_SEMI"] = "0"
main.master(pcm, "listen/%s_nopitch.mp3" % label, DEMO, 0.7, use_music=True)
os.environ["PITCH_SEMI"] = "3"
main.master(pcm, "listen/%s_pitchdown.mp3" % label, DEMO, 0.7, use_music=True)
print("rendered listen/%s_nopitch.mp3 and listen/%s_pitchdown.mp3" % (label, label))
