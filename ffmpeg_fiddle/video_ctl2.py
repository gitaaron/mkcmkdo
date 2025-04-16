cmd="ffmpeg -i in.mp4 -y out.avi"
process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,universal_newlines=True)
for line in process.stdout:
    print(line)