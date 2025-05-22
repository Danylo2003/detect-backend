# cameras/consumers.py

import json
import logging
import base64
from typing import Dict, Any
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from utils.camera_stream_manager import stream_manager

logger = logging.getLogger('security_ai')

class CameraStreamConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for camera streaming"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.camera_id = None
        self.session_id = None
        self.group_name = None
        self.user = None
    
    async def connect(self):
        """Handle WebSocket connection"""
        try:
            # Get camera ID from URL
            self.camera_id = self.scope['url_route']['kwargs']['camera_id']
            self.user = self.scope.get('user')
            
            # Check authentication
            if isinstance(self.user, AnonymousUser) or not self.user.is_authenticated:
                await self.close(code=4001)  # Unauthorized
                return
            
            # Check camera access permissions
            if not await self.check_camera_access():
                await self.close(code=4003)  # Forbidden
                return
            
            # Generate session ID
            import uuid
            self.session_id = str(uuid.uuid4())
            
            # Join camera group
            self.group_name = f"camera_{self.camera_id}"
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            
            # Accept connection
            await self.accept()
            
            # Send connection confirmation
            await self.send(text_data=json.dumps({
                'type': 'connection_established',
                'camera_id': self.camera_id,
                'session_id': self.session_id,
                'message': 'Connected to camera stream'
            }))
            
            logger.info(f"WebSocket connected: camera {self.camera_id}, user {self.user.id}")
            
        except Exception as e:
            logger.error(f"Error in WebSocket connect: {str(e)}")
            await self.close(code=4000)  # General error
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        try:
            # Stop streaming
            if self.camera_id and self.session_id:
                await database_sync_to_async(stream_manager.stop_stream)(
                    self.camera_id, self.session_id
                )
            
            # Leave camera group
            if self.group_name:
                await self.channel_layer.group_discard(self.group_name, self.channel_name)
            
            logger.info(f"WebSocket disconnected: camera {self.camera_id}, session {self.session_id}")
            
        except Exception as e:
            logger.error(f"Error in WebSocket disconnect: {str(e)}")
    
    async def receive(self, text_data):
        """Handle messages from WebSocket"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'start_stream':
                await self.handle_start_stream(data)
            elif message_type == 'stop_stream':
                await self.handle_stop_stream(data)
            elif message_type == 'change_quality':
                await self.handle_change_quality(data)
            elif message_type == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))
            else:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': f'Unknown message type: {message_type}'
                }))
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Internal server error'
            }))
    
    async def handle_start_stream(self, data):
        """Handle start stream request"""
        try:
            quality = data.get('quality', 'medium')
            
            # Get camera details
            camera = await self.get_camera()
            if not camera:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Camera not found'
                }))
                return
            
            # Start streaming
            success = await database_sync_to_async(stream_manager.start_stream)(
                self.camera_id,
                str(self.user.id),
                self.session_id,
                camera.stream_url,
                quality
            )
            
            if success:
                await self.send(text_data=json.dumps({
                    'type': 'stream_started',
                    'camera_id': self.camera_id,
                    'session_id': self.session_id,
                    'quality': quality
                }))
            else:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Failed to start stream'
                }))
                
        except Exception as e:
            logger.error(f"Error starting stream: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Failed to start stream'
            }))
    
    async def handle_stop_stream(self, data):
        """Handle stop stream request"""
        try:
            success = await database_sync_to_async(stream_manager.stop_stream)(
                self.camera_id, self.session_id
            )
            
            if success:
                await self.send(text_data=json.dumps({
                    'type': 'stream_stopped',
                    'camera_id': self.camera_id,
                    'session_id': self.session_id
                }))
            else:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Failed to stop stream'
                }))
                
        except Exception as e:
            logger.error(f"Error stopping stream: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Failed to stop stream'
            }))
    
    async def handle_change_quality(self, data):
        """Handle quality change request"""
        try:
            quality = data.get('quality', 'medium')
            
            # Stop current stream
            await database_sync_to_async(stream_manager.stop_stream)(
                self.camera_id, self.session_id
            )
            
            # Get camera details
            camera = await self.get_camera()
            if not camera:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Camera not found'
                }))
                return
            
            # Start stream with new quality
            success = await database_sync_to_async(stream_manager.start_stream)(
                self.camera_id,
                str(self.user.id),
                self.session_id,
                camera.stream_url,
                quality
            )
            
            if success:
                await self.send(text_data=json.dumps({
                    'type': 'quality_changed',
                    'camera_id': self.camera_id,
                    'session_id': self.session_id,
                    'quality': quality
                }))
            else:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Failed to change quality'
                }))
                
        except Exception as e:
            logger.error(f"Error changing quality: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Failed to change quality'
            }))
    
    async def stream_frame(self, event):
        """Send frame to WebSocket client"""
        try:
            # Only send frames for our session
            if event.get('session_id') != self.session_id:
                return
            
            # Encode frame as base64
            frame_b64 = base64.b64encode(event['frame']).decode('utf-8')
            
            await self.send(text_data=json.dumps({
                'type': 'frame',
                'camera_id': event['camera_id'],
                'session_id': event['session_id'],
                'frame': frame_b64,
                'frame_number': event['frame_number'],
                'timestamp': event['timestamp']
            }))
            
        except Exception as e:
            logger.error(f"Error sending frame: {str(e)}")
    
    @database_sync_to_async
    def check_camera_access(self):
        """Check if user has access to the camera"""
        try:
            from cameras.models import Camera
            camera = Camera.objects.filter(id=self.camera_id).first()
            
            if not camera:
                return False
            
            # Check if user owns the camera or is admin
            if camera.user == self.user or self.user.is_admin():
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking camera access: {str(e)}")
            return False
    
    @database_sync_to_async
    def get_camera(self):
        """Get camera object"""
        try:
            from cameras.models import Camera
            return Camera.objects.filter(id=self.camera_id).first()
        except Exception as e:
            logger.error(f"Error getting camera: {str(e)}")
            return None


class CameraStatsConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for camera statistics"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.camera_id = None
        self.user = None
    
    async def connect(self):
        """Handle WebSocket connection"""
        try:
            # Get camera ID from URL
            self.camera_id = self.scope['url_route']['kwargs']['camera_id']
            self.user = self.scope.get('user')
            
            # Check authentication
            if isinstance(self.user, AnonymousUser) or not self.user.is_authenticated:
                await self.close(code=4001)  # Unauthorized
                return
            
            # Check camera access permissions
            if not await self.check_camera_access():
                await self.close(code=4003)  # Forbidden
                return
            
            # Accept connection
            await self.accept()
            
            # Send initial stats
            await self.send_stats()
            
            logger.info(f"Stats WebSocket connected: camera {self.camera_id}, user {self.user.id}")
            
        except Exception as e:
            logger.error(f"Error in stats WebSocket connect: {str(e)}")
            await self.close(code=4000)  # General error
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        logger.info(f"Stats WebSocket disconnected: camera {self.camera_id}")
    
    async def receive(self, text_data):
        """Handle messages from WebSocket"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'get_stats':
                await self.send_stats()
            elif message_type == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))
            
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
        except Exception as e:
            logger.error(f"Error handling stats WebSocket message: {str(e)}")
    
    async def send_stats(self):
        """Send camera statistics"""
        try:
            stats = await database_sync_to_async(stream_manager.get_stream_stats)(self.camera_id)
            
            await self.send(text_data=json.dumps({
                'type': 'stats',
                'data': stats
            }))
            
        except Exception as e:
            logger.error(f"Error sending stats: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Failed to get stats'
            }))
    
    @database_sync_to_async
    def check_camera_access(self):
        """Check if user has access to the camera"""
        try:
            from cameras.models import Camera
            camera = Camera.objects.filter(id=self.camera_id).first()
            
            if not camera:
                return False
            
            # Check if user owns the camera or is admin
            if camera.user == self.user or self.user.is_admin():
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking camera access: {str(e)}")
            return False