import ffmpeg, time

#Setup for recording windows desktop to mp4 file
process = (
			ffmpeg
			.input(format='gdigrab',framerate=25,filename="desktop")
			.output(crf="0",preset="ultrafast",filename="./output.mp4",c= "libx264" )
			.overwrite_output()
			)
#Launch video recording
process = process.run_async(pipe_stdin=True)


#Stop video recording
process.communicate(str.encode("q")) #Equivalent to send a Q

# To be sure that the process ends I wait 3 seconds and then terminate de process (wich is more like kill -9)
time.sleep(3) 
process.terminate()