from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count
from django.utils import timezone
import datetime
import os
from django.conf import settings
from django.http import FileResponse
import logging

from .models import Alert
from .serializers import (
    AlertSerializer, AlertListSerializer, AlertCreateSerializer,
    AlertStatusUpdateSerializer, AlertSummarySerializer
)
from utils.permissions import IsOwnerOrAdmin

logger = logging.getLogger('security_ai')

class AlertViewSet(viewsets.ModelViewSet):
    """ViewSet for managing alerts."""
    
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]
    serializer_class = AlertSerializer
    
    def get_queryset(self):
        """Return alerts based on user permissions."""
        user = self.request.user
        
        # For admin users, return all alerts
        if user.is_admin():
            queryset = Alert.objects.all()
        else:
            # For regular users, return alerts from their cameras
            queryset = Alert.objects.filter(camera__user=user)
        
        # Apply filters if provided
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        alert_type = self.request.query_params.get('type')
        if alert_type:
            queryset = queryset.filter(alert_type=alert_type)
        
        severity = self.request.query_params.get('severity')
        if severity:
            queryset = queryset.filter(severity=severity)
        
        camera_id = self.request.query_params.get('camera_id')
        if camera_id:
            queryset = queryset.filter(camera_id=camera_id)
        
        # Date range filters
        start_date = self.request.query_params.get('start_date')
        if start_date:
            try:
                start_date = datetime.datetime.strptime(start_date, '%Y-%m-%d').date()
                queryset = queryset.filter(detection_time__date__gte=start_date)
            except ValueError:
                pass
        
        end_date = self.request.query_params.get('end_date')
        if end_date:
            try:
                end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d').date()
                queryset = queryset.filter(detection_time__date__lte=end_date)
            except ValueError:
                pass
        
        return queryset
    
    def get_serializer_class(self):
        """Return appropriate serializer class based on the action."""
        if self.action == 'list':
            return AlertListSerializer
        elif self.action == 'create':
            return AlertCreateSerializer
        elif self.action == 'update_status':
            return AlertStatusUpdateSerializer
        return self.serializer_class
    
    def list(self, request, *args, **kwargs):
        """List alerts with pagination."""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data = {
                'success': True,
                'data': response.data,
                'message': 'Alerts retrieved successfully.',
                'errors': []
            }
            return response
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
            'message': 'Alerts retrieved successfully.',
            'errors': []
        })
    
    def retrieve(self, request, *args, **kwargs):
        """Retrieve a specific alert."""
        instance = self.get_object()
        serializer = AlertSerializer(instance)
        
        return Response({
            'success': True,
            'data': serializer.data,
            'message': 'Alert retrieved successfully.',
            'errors': []
        })
    
    def create(self, request, *args, **kwargs):
        """Create a new alert."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        alert = serializer.save()
        
        headers = self.get_success_headers(serializer.data)
        return Response({
            'success': True,
            'data': AlertSerializer(alert).data,
            'message': 'Alert created successfully.',
            'errors': []
        }, status=status.HTTP_201_CREATED, headers=headers)
    
    @action(detail=True, methods=['put', 'patch'])
    def status(self, request, pk=None):
        """Update the status of an alert."""
        alert = self.get_object()
        serializer = AlertStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        new_status = serializer.validated_data['status']
        notes = serializer.validated_data.get('notes')
        
        if notes:
            alert.add_notes(notes)
        
        if new_status == 'confirmed':
            alert.mark_as_confirmed(request.user)
        elif new_status == 'dismissed':
            alert.mark_as_dismissed(request.user)
        elif new_status == 'false_positive':
            alert.mark_as_false_positive(request.user)
        
        return Response({
            'success': True,
            'data': AlertSerializer(alert).data,
            'message': f'Alert status updated to {new_status}.',
            'errors': []
        })
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get alert summary statistics."""
        queryset = self.get_queryset()
        
        # Get total counts
        total_alerts = queryset.count()
        new_alerts = queryset.filter(status='new').count()
        confirmed_alerts = queryset.filter(status='confirmed').count()
        dismissed_alerts = queryset.filter(status='dismissed').count()
        false_positive_alerts = queryset.filter(status='false_positive').count()
        
        # Get counts by type
        by_type = dict(queryset.values('alert_type').annotate(count=Count('id')).values_list('alert_type', 'count'))
        
        # Get counts by severity
        by_severity = dict(queryset.values('severity').annotate(count=Count('id')).values_list('severity', 'count'))
        
        # Get daily counts for the last 7 days
        today = timezone.now().date()
        daily_count = []
        
        for i in range(6, -1, -1):
            date = today - datetime.timedelta(days=i)
            count = queryset.filter(detection_time__date=date).count()
            daily_count.append({
                'date': date.strftime('%Y-%m-%d'),
                'count': count
            })
        
        # Get weekly counts for the last 4 weeks
        weekly_count = []
        
        for i in range(3, -1, -1):
            start_date = today - datetime.timedelta(days=(i+1)*7)
            end_date = today - datetime.timedelta(days=i*7)
            count = queryset.filter(detection_time__date__gt=start_date, detection_time__date__lte=end_date).count()
            weekly_count.append({
                'week': f"Week {4-i}",
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'count': count
            })
        
        # Get monthly counts for the last 6 months
        monthly_count = []
        
        for i in range(5, -1, -1):
            # Get the first day of the month
            first_day = (today.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)
            first_day = first_day.replace(month=((today.month - i - 1) % 12) + 1)
            if first_day.month > today.month:
                first_day = first_day.replace(year=today.year - 1)
            
            # Get the last day of the month
            if i > 0:
                last_day = (first_day.replace(month=first_day.month % 12 + 1, day=1) - datetime.timedelta(days=1))
            else:
                last_day = today
            
            count = queryset.filter(detection_time__date__gte=first_day, detection_time__date__lte=last_day).count()
            monthly_count.append({
                'month': first_day.strftime('%B %Y'),
                'start_date': first_day.strftime('%Y-%m-%d'),
                'end_date': last_day.strftime('%Y-%m-%d'),
                'count': count
            })
        
        summary_data = {
            'total_alerts': total_alerts,
            'new_alerts': new_alerts,
            'confirmed_alerts': confirmed_alerts,
            'dismissed_alerts': dismissed_alerts,
            'false_positive_alerts': false_positive_alerts,
            'by_type': by_type,
            'by_severity': by_severity,
            'daily_count': daily_count,
            'weekly_count': weekly_count,
            'monthly_count': monthly_count
        }
        
        serializer = AlertSummarySerializer(summary_data)
        
        return Response({
            'success': True,
            'data': serializer.data,
            'message': 'Alert summary retrieved successfully.',
            'errors': []
        })
    
    @action(detail=True, methods=['get'])
    def video(self, request, pk=None):
        """Get video file for a specific alert."""
        alert = self.get_object()
        
        if not alert.video_file:
            return Response({
                'success': False,
                'data': {},
                'message': 'No video file available for this alert.',
                'errors': ['Video file not found.']
            }, status=status.HTTP_404_NOT_FOUND)
        
        try:
            # Get the file path
            file_path = os.path.join(settings.MEDIA_ROOT, str(alert.video_file))
            
            # Check if file exists
            if not os.path.exists(file_path):
                return Response({
                    'success': False,
                    'data': {},
                    'message': 'Video file not found on the server.',
                    'errors': ['File does not exist.']
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Return the file
            response = FileResponse(open(file_path, 'rb'))
            response['Content-Disposition'] = f'inline; filename="{os.path.basename(file_path)}"'
            return response
            
        except Exception as e:
            logger.error(f"Error retrieving video file for alert {alert.id}: {str(e)}")
            return Response({
                'success': False,
                'data': {},
                'message': 'Error retrieving video file.',
                'errors': [str(e)]
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)