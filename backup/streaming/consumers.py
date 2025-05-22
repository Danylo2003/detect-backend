# streaming/consumers.py
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger('security_ai')

class CameraStreamConsumer(AsyncWebsocketConsumer):
    
    async def connect(self):
        self.group_name = self.scope['url_route']['kwargs']['group_name']
        self.user = self.scope.get('user', AnonymousUser())
        
        if self.user.is_anonymous:
            await self.close()
            return
        
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()
        logger.info(f"WebSocket connected: {self.group_name} (User: {self.user.email})")
        
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'Connected stream!',
            'group_name': self.group_name
        }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
        logger.info(f"WebSocket disconnected: {self.group_name}")

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type', '')
            
            if message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': text_data_json.get('timestamp')
                }))
            elif message_type == 'request_frame':
                pass
            else:
                logger.warning(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError:
            logger.error("Received wrong message")
        except Exception as e:
            logger.error(f"Message processing error: {e}")

    async def send_frame(self, event):
        try:
            frame = event['frame']
            metadata = event.get('metadata', {})
            
            await self.send(text_data=json.dumps({
                'type': 'video_frame',
                'frame': frame,
                'metadata': metadata
            }))
            
        except Exception as e:
            logger.error(f"Frame transform error: {e}")

    async def send_detection(self, event):
        try:
            detection = event['detection']
            
            await self.send(text_data=json.dumps({
                'type': 'detection_result',
                'detection': detection
            }))
            
        except Exception as e:
            logger.error(f"Detect result error: {e}")

    async def send_alert(self, event):
        try:
            alert = event['alert']
            
            await self.send(text_data=json.dumps({
                'type': 'alert',
                'alert': alert
            }))
            
        except Exception as e:
            logger.error(f"Alert transform failed: {e}")

    async def send_error(self, event):
        try:
            error = event['error']
            
            await self.send(text_data=json.dumps({
                'type': 'error',
                'error': error
            }))
            
        except Exception as e:
            logger.error(f"Message transform failed: {e}")

    @database_sync_to_async
    def get_camera_by_id(self, camera_id):
        try:
            from cameras.models import Camera
            return Camera.objects.get(id=camera_id, user=self.user)
        except Camera.DoesNotExist:
            return None