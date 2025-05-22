import cv2

def resize_frame(frame, scale=0.3):
    """
    Resize the video frame by a given scale.
    
    Args:
    - frame: The video frame to resize.
    - scale: The scale factor (default is 0.75).
    
    Returns:
    - The resized frame.
    """
    width = int(frame.shape[1] * scale)
    height = int(frame.shape[0] * scale)
    dimensions = (800, 600)

    return cv2.resize(frame, dimensions, interpolation=cv2.INTER_AREA)

def display_rtsp_feed(rtsp_url, scale=0.75):
    """
    Open an RTSP video feed, resize its frames, and display them.
    
    Args:
    - rtsp_url: The RTSP URL of the video feed.
    - scale: The scale factor to resize frames (default is 0.75).
    """
    # Open the RTSP stream
    cap = cv2.VideoCapture(rtsp_url)

    if not cap.isOpened():
        print("Error opening video stream")
        return

    while True:
        ret, frame = cap.read()
        if ret:
            # Resize the frame
            resized_frame = resize_frame(frame, scale=scale)
            
            # Display the resized frame
            cv2.imshow('Resized RTSP Feed', resized_frame)

            # Break the loop when 'q' is pressed
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        else:
            break

    # When everything done, release the video capture object
    cap.release()
    cv2.destroyAllWindows()


rtsp_url = 'http://185.133.99.214:8010/mjpg/video.mjpg'
display_rtsp_feed(rtsp_url)