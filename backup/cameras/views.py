from rest_framework import viewsets, generics, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
import cv2
import logging

from .models import Camera
from .serializers import (
    CameraSerializer, CameraCreateSerializer, CameraUpdateSerializer,
    CameraStatusSerializer, CameraListSerializer, CameraSettingsSerializer
)
from utils.permissions import IsOwnerOrAdmin
from streaming.stream_manager import stream_manager
logger = logging.getLogger('security_ai')

class CameraViewSet(viewsets.ModelViewSet):
    """ViewSet for managing cameras."""
    
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]
    serializer_class = CameraSerializer
    
    def get_queryset(self):
        """Return all cameras for admins, or just the user's cameras for regular users."""
        user = self.request.user
        if user.is_admin():
            return Camera.objects.all()
        return Camera.objects.filter(user=user)
    
    def get_serializer_class(self):
        """Return appropriate serializer class based on the action."""
        if self.action == 'create':
            return CameraCreateSerializer
        elif self.action == 'update' or self.action == 'partial_update':
            return CameraUpdateSerializer
        elif self.action == 'list':
            return CameraListSerializer
        elif self.action == 'update_status':
            return CameraStatusSerializer
        elif self.action == 'settings':
            return CameraSettingsSerializer
        return self.serializer_class
    
    def create(self, request, *args, **kwargs):
        """Create a new camera."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        camera = serializer.save()

        connection_status = self._check_camera_connection(camera)
        camera.status = connection_status
        if connection_status == 'online':
            camera.last_online = timezone.now()
        camera.save(update_fields=['status', 'last_online', 'updated_at'])
        headers = self.get_success_headers(serializer.data)
        return Response({
            'success': True,
            'data': CameraSerializer(camera).data,
            'message': 'Camera created successfully.',
            'errors': []
        }, status=status.HTTP_201_CREATED, headers=headers)
    
    def update(self, request, *args, **kwargs):
        """Update a camera."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        camera = serializer.save()
        
        return Response({
            'success': True,
            'data': CameraSerializer(camera).data,
            'message': 'Camera updated successfully.',
            'errors': []
        })
    
    def retrieve(self, request, *args, **kwargs):
        """Retrieve a camera."""
        instance = self.get_object()
        serializer = CameraSerializer(instance)
        
        return Response({
            'success': True,
            'data': serializer.data,
            'message': 'Camera retrieved successfully.',
            'errors': []
        })
    
    def list(self, request, *args, **kwargs):
        """List cameras."""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data = {
                'success': True,
                'data': response.data,
                'message': 'Cameras retrieved successfully.',
                'errors': []
            }
            return response
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
            'message': 'Cameras retrieved successfully.',
            'errors': []
        })
    
    def destroy(self, request, *args, **kwargs):
        """Delete a camera."""
        instance = self.get_object()
        camera_id = instance.id
        stream_manager.stop_camera_stream(camera_id)
        self.perform_destroy(instance)
        
        return Response({
            'success': True,
            'data': {},
            'message': 'Camera deleted successfully.',
            'errors': []
        }, status=status.HTTP_200_OK)

    def _check_camera_connection(self, camera):
        try:
            stream_url = camera.get_stream_url()
            cap = cv2.VideoCapture(stream_url)
            if cap.isOpened():
                ret, _ = cap.read()
                cap.release()
                if ret:
                    logger.info(f"Camera connection successful: {camera.id} - {camera.name}")
                    return 'online'
                else:
                    logger.warning(f"Camera connected but failed to read frame: {camera.id} - {camera.name}")
                    return 'error'
            else:
                logger.warning(f"Failed to connect to camera: {camera.id} - {camera.name}")
                return 'offline'
        except Exception as e:
            logger.error(f"Error checking camera connection: {camera.id} - {camera.name} - {str(e)}")
            return 'error'
    
    @action(detail=True, methods=['get'])
    def stream(self, request, pk=None):
        """Get camera livestream URL for HLS streaming."""
        try:
            camera = self.get_object()
            camera_id = camera.id
            use_gstreamer = request.query_params.get('gstreamer', 'true').lower() == 'true'
            # result = stream_manager.start_camera_stream(camera_id, use_gstreamer)
            print(use_gstreamer)
            if result['success']:
                return Response({
                    'success': True,
                    'data': {
                        'session_id': result['session_id'],
                        'group_name': result['group_name'],
                        'stream_type': result['stream_type'],
                        'websocket_url': f"/ws/stream/{result['group_name']}/",
                        'camera_info': {
                            'id': camera.id,
                            'name': camera.name,
                            'location': camera.location,
                            'detection_enabled': camera.detection_enabled
                        }
                    },
                    'message': 'Stream started successfully.',
                    'errors': []
                })
            else:
                return Response({
                    'success': False,
                    'data': {},
                    'message': 'Failed to start stream.',
                    'errors': [result.get('error', 'Unknown error')]
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        except Camera.DoesNotExist:
            return Response({
                'success': False,
                'data': {},
                'message': 'Camera not found',
                'errors': ['Invalid camera ID']
            }, status=status.HTTP_404_NOT_FOUND)
        
        except Exception as e:
            logger.error(f"Stream URL retrieval error: {str(e)}")
            return Response({
                'success': False,
                'data': {},
                'message': 'Error retrieving stream URL',
                'errors': [str(e)]
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def status(self, request):
        """Get the status of all cameras."""
        cameras = self.get_queryset()
        serializer = CameraStatusSerializer(cameras, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data,
            'message': 'Camera statuses retrieved successfully.',
            'errors': []
        })
    
    # @action(detail=True, methods=['get', 'put', 'patch'])
    # def settings(self, request, pk=None):
    #     """Get or update camera detection settings."""
    #     camera = self.get_object()
        
    #     if request.method == 'GET':
    #         serializer = CameraSettingsSerializer(camera)
    #         return Response({
    #             'success': True,
    #             'data': serializer.data,
    #             'message': 'Camera settings retrieved successfully.',
    #             'errors': []
    #         })
        
    #     serializer = CameraSettingsSerializer(camera, data=request.data, partial=True)
    #     serializer.is_valid(raise_exception=True)
    #     camera = serializer.save()
        
    #     return Response({
    #         'success': True,
    #         'data': serializer.data,
    #         'message': 'Camera settings updated successfully.',
    #         'errors': []
    #     })