# streaming/views.py
import json
import logging
import time
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings

from .stream_manager import stream_manager
from cameras.models import Camera
from utils.permissions import IsOwnerOrAdmin

logger = logging.getLogger('security_ai')

class StreamingViewSet(viewsets.GenericViewSet):
    
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]
    
    @action(detail=False, methods=['get'])
    def health(self, request):
        try:
            redis_status = 'healthy'
            try:
                stream_manager.redis_client.ping()
            except Exception as e:
                redis_status = f'unhealthy: {str(e)}'
            
            active_streams_count = len(stream_manager.active_streams)
            
            system_status = {
                'redis': redis_status,
                'active_streams': active_streams_count,
                'max_concurrent_streams': settings.STREAMING_SETTINGS['MAX_CONCURRENT_STREAMS'],
                'background_tasks': stream_manager.background_tasks_running
            }
            
            overall_status = 'healthy' if redis_status == 'healthy' else 'degraded'
            
            return Response({
                'success': True,
                'data': {
                    'status': overall_status,
                    'details': system_status
                },
                'message': 'Streaming system health check completed.',
                'errors': []
            })
            
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return Response({
                'success': False,
                'data': {},
                'message': 'Health check failed.',
                'errors': [str(e)]
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def active_streams(self, request):
        try:
            user = request.user
            active_streams = []
            
            for camera_id, streamer in stream_manager.active_streams.items():
                try:
                    camera = Camera.objects.get(id=camera_id)
                    if not user.is_admin() and camera.user != user:
                        continue
                    
                    metrics = streamer.get_metrics()
                    
                    from .stream_manager import GStreamerAIStreamer
                    stream_type = 'gstreamer' if isinstance(streamer, GStreamerAIStreamer) else 'opencv'
                    
                    stream_info = {
                        'camera_id': camera_id,
                        'camera_name': camera.name,
                        'session_id': streamer.session_id,
                        'group_name': streamer.group_name,
                        'stream_type': stream_type,
                        'metrics': metrics
                    }
                    active_streams.append(stream_info)
                    
                except Camera.DoesNotExist:
                    continue
            
            return Response({
                'success': True,
                'data': {
                    'active_streams': active_streams,
                    'total_count': len(active_streams)
                },
                'message': 'Active streams retrieved successfully.',
                'errors': []
            })
            
        except Exception as e:
            logger.error(f"Active streams query error: {e}")
            return Response({
                'success': False,
                'data': {},
                'message': 'Error retrieving active streams.',
                'errors': [str(e)]
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def stop_all_streams(self, request):
        try:
            if not request.user.is_admin():
                return Response({
                    'success': False,
                    'data': {},
                    'message': 'Admin permission required.',
                    'errors': ['Permission denied']
                }, status=status.HTTP_403_FORBIDDEN)
            
            stopped_streams = []
            
            active_cameras = list(stream_manager.active_streams.keys())
            
            for camera_id in active_cameras:
                result = stream_manager.stop_camera_stream(camera_id)
                stopped_streams.append({
                    'camera_id': camera_id,
                    'result': result
                })
            
            return Response({
                'success': True,
                'data': {
                    'stopped_streams': stopped_streams,
                    'total_stopped': len(stopped_streams)
                },
                'message': 'All streams stopped successfully.',
                'errors': []
            })
            
        except Exception as e:
            logger.error(f"Stop all streams error: {e}")
            return Response({
                'success': False,
                'data': {},
                'message': 'Error stopping all streams.',
                'errors': [str(e)]
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def system_metrics(self, request):
        try:
            redis_info = stream_manager.redis_client.info('memory')
            
            active_sessions = stream_manager.redis_client.smembers("active_sessions")
            
            total_frames = 0
            total_detections = 0
            stream_metrics = []
            
            for camera_id, streamer in stream_manager.active_streams.items():
                metrics = streamer.get_metrics()
                total_frames += metrics.get('frame_count', 0)
                total_detections += metrics.get('detection_count', 0)
                stream_metrics.append({
                    'camera_id': camera_id,
                    'metrics': metrics
                })
            
            system_metrics = {
                'redis': {
                    'memory_used': redis_info.get('used_memory_human', 'N/A'),
                    'connected_clients': redis_info.get('connected_clients', 0)
                },
                'streaming': {
                    'active_streams': len(stream_manager.active_streams),
                    'active_sessions': len(active_sessions),
                    'total_frames_processed': total_frames,
                    'total_detections': total_detections
                },
                'individual_streams': stream_metrics
            }
            
            return Response({
                'success': True,
                'data': system_metrics,
                'message': 'System metrics retrieved successfully.',
                'errors': []
            })
            
        except Exception as e:
            logger.error(f"System metrics error: {e}")
            return Response({
                'success': False,
                'data': {},
                'message': 'Error retrieving system metrics.',
                'errors': [str(e)]
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def start_stream(self, request):
        try:
            camera_id = request.data.get('camera_id')
            use_gstreamer = request.data.get('use_gstreamer', True)
            
            if not camera_id:
                return Response({
                    'success': False,
                    'data': {},
                    'message': 'Camera ID is required.',
                    'errors': ['camera_id field is required']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                camera = Camera.objects.get(id=camera_id)
                if not request.user.is_admin() and camera.user != request.user:
                    return Response({
                        'success': False,
                        'data': {},
                        'message': 'Permission denied.',
                        'errors': ['You do not have permission to access this camera']
                    }, status=status.HTTP_403_FORBIDDEN)
            except Camera.DoesNotExist:
                return Response({
                    'success': False,
                    'data': {},
                    'message': 'Camera not found.',
                    'errors': ['Invalid camera ID']
                }, status=status.HTTP_404_NOT_FOUND)
            
            result = stream_manager.start_camera_stream(camera_id, use_gstreamer)
            
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
                
        except Exception as e:
            logger.error(f"Start stream error: {e}")
            return Response({
                'success': False,
                'data': {},
                'message': 'Error starting stream.',
                'errors': [str(e)]
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def stop_stream(self, request):
        try:
            camera_id = request.data.get('camera_id')
            
            if not camera_id:
                return Response({
                    'success': False,
                    'data': {},
                    'message': 'Camera ID is required.',
                    'errors': ['camera_id field is required']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                camera = Camera.objects.get(id=camera_id)
                if not request.user.is_admin() and camera.user != request.user:
                    return Response({
                        'success': False,
                        'data': {},
                        'message': 'Permission denied.',
                        'errors': ['You do not have permission to access this camera']
                    }, status=status.HTTP_403_FORBIDDEN)
            except Camera.DoesNotExist:
                return Response({
                    'success': False,
                    'data': {},
                    'message': 'Camera not found.',
                    'errors': ['Invalid camera ID']
                }, status=status.HTTP_404_NOT_FOUND)
            
            result = stream_manager.stop_camera_stream(camera_id)
            
            return Response({
                'success': result['success'],
                'data': {},
                'message': result.get('message', 'Stream operation completed.'),
                'errors': [result.get('error')] if not result['success'] else []
            })
            
        except Exception as e:
            logger.error(f"Stop stream error: {e}")
            return Response({
                'success': False,
                'data': {},
                'message': 'Error stopping stream.',
                'errors': [str(e)]
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def stream_status(self, request):
        try:
            camera_id = request.query_params.get('camera_id')
            
            if not camera_id:
                return Response({
                    'success': False,
                    'data': {},
                    'message': 'Camera ID is required.',
                    'errors': ['camera_id parameter is required']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                camera_id = int(camera_id)
            except ValueError:
                return Response({
                    'success': False,
                    'data': {},
                    'message': 'Invalid camera ID.',
                    'errors': ['camera_id must be a valid integer']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                camera = Camera.objects.get(id=camera_id)
                if not request.user.is_admin() and camera.user != request.user:
                    return Response({
                        'success': False,
                        'data': {},
                        'message': 'Permission denied.',
                        'errors': ['You do not have permission to access this camera']
                    }, status=status.HTTP_403_FORBIDDEN)
            except Camera.DoesNotExist:
                return Response({
                    'success': False,
                    'data': {},
                    'message': 'Camera not found.',
                    'errors': ['Invalid camera ID']
                }, status=status.HTTP_404_NOT_FOUND)
            
            result = stream_manager.get_stream_status(camera_id)
            
            return Response({
                'success': result['success'],
                'data': {
                    'camera_id': camera_id,
                    'is_streaming': result.get('is_active', False),
                    'session_id': result.get('session_id'),
                    'group_name': result.get('group_name'),
                    'metrics': result.get('metrics')
                },
                'message': 'Stream status retrieved successfully.',
                'errors': [result.get('error')] if not result['success'] else []
            })
            
        except Exception as e:
            logger.error(f"Stream status error: {e}")
            return Response({
                'success': False,
                'data': {},
                'message': 'Error retrieving stream status.',
                'errors': [str(e)]
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@require_http_methods(["GET"])
def get_cached_frame(request):
    try:
        session_id = request.GET.get('session_id')
        
        if not session_id:
            return JsonResponse({
                'success': False,
                'message': 'I need session ID',
                'errors': ['session_id parameter is required']
            }, status=400)
        
        frame_data = stream_manager.redis_client.get(f"frame:{session_id}")
        metadata = stream_manager.redis_client.get(f"frame_meta:{session_id}")
        
        if frame_data and metadata:
            return JsonResponse({
                'success': True,
                'data': {
                    'frame': frame_data,
                    'metadata': json.loads(metadata)
                },
                'message': 'Cached frame retrieved successfully.',
                'errors': []
            })
        else:
            return JsonResponse({
                'success': False,
                'data': {},
                'message': 'No cached frame available.',
                'errors': ['No cached frame found for this session']
            }, status=404)
            
    except Exception as e:
        logger.error(f"Get cached frame error: {e}")
        return JsonResponse({
            'success': False,
            'data': {},
            'message': 'Error retrieving cached frame.',
            'errors': [str(e)]
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def get_session_info(request):
    try:
        session_id = request.GET.get('session_id')
        
        if session_id:
            session_data = stream_manager.redis_client.get(f"session:{session_id}")
            if session_data:
                return JsonResponse({
                    'success': True,
                    'data': {
                        'session': json.loads(session_data)
                    },
                    'message': 'Session info retrieved successfully.',
                    'errors': []
                })
            else:
                return JsonResponse({
                    'success': False,
                    'data': {},
                    'message': 'Session not found.',
                    'errors': ['Invalid session ID']
                }, status=404)
        else:
            session_keys = stream_manager.redis_client.keys("session:*")
            sessions = []
            
            for key in session_keys:
                session_data = stream_manager.redis_client.get(key)
                if session_data:
                    sessions.append(json.loads(session_data))
            
            return JsonResponse({
                'success': True,
                'data': {
                    'sessions': sessions,
                    'total_count': len(sessions)
                },
                'message': 'All sessions retrieved successfully.',
                'errors': []
            })
            
    except Exception as e:
        logger.error(f"Get session info error: {e}")
        return JsonResponse({
            'success': False,
            'data': {},
            'message': 'Error retrieving session info.',
            'errors': [str(e)]
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def cleanup_sessions(request):
    try:
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            return JsonResponse({
                'success': False,
                'message': 'Authentication required.',
                'errors': ['Authorization header is required']
            }, status=401)
        
        current_time = time.time()
        expired_threshold = current_time - settings.STREAMING_SETTINGS['SESSION_TIMEOUT']
        
        cleaned_sessions = []
        active_sessions = stream_manager.redis_client.smembers("active_sessions")
        
        for session_id in active_sessions:
            session_data = stream_manager.redis_client.get(f"session:{session_id}")
            if session_data:
                session = json.loads(session_data)
                created_at = session.get('created_at', 0)
                
                if created_at < expired_threshold:
                    stream_manager._cleanup_session(session_id)
                    cleaned_sessions.append(session_id)
        
        return JsonResponse({
            'success': True,
            'data': {
                'cleaned_sessions': cleaned_sessions,
                'count': len(cleaned_sessions)
            },
            'message': f'Cleaned up {len(cleaned_sessions)} expired sessions.',
            'errors': []
        })
        
    except Exception as e:
        logger.error(f"Cleanup sessions error: {e}")
        return JsonResponse({
            'success': False,
            'data': {},
            'message': 'Error cleaning up sessions.',
            'errors': [str(e)]
        }, status=500)