from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.http import Http404
from rest_framework.exceptions import (
    AuthenticationFailed, NotAuthenticated, PermissionDenied,
    ValidationError, NotFound, MethodNotAllowed, Throttled
)

def custom_exception_handler(exc, context):
    """
    Custom exception handler for consistent API responses.
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    # If this is a Django Http404 exception, convert to DRF NotFound
    if isinstance(exc, Http404):
        exc = NotFound()
        response = exception_handler(exc, context)
    
    # If unexpected error occurs (server error, etc.)
    if response is None:
        return Response({
            'success': False,
            'data': {},
            'message': 'Server error, please try again later.',
            'errors': [str(exc)]
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    error_response = {
        'success': False,
        'data': {},
        'message': '',
        'errors': []
    }
    
    if isinstance(exc, ValidationError):
        error_response['message'] = 'Validation error.'
        
        # Extract validation errors
        if isinstance(exc.detail, dict):
            for key, value in exc.detail.items():
                if isinstance(value, list):
                    for error in value:
                        error_response['errors'].append(f"{key}: {error}")
                else:
                    error_response['errors'].append(f"{key}: {value}")
        elif isinstance(exc.detail, list):
            for error in exc.detail:
                error_response['errors'].append(error)
        else:
            error_response['errors'].append(str(exc.detail))
            
    elif isinstance(exc, NotAuthenticated):
        error_response['message'] = 'Authentication credentials were not provided.'
        error_response['errors'].append('You must be logged in to access this resource.')
        
    elif isinstance(exc, AuthenticationFailed):
        error_response['message'] = 'Authentication failed.'
        error_response['errors'].append('Invalid authentication credentials.')
        
    elif isinstance(exc, PermissionDenied):
        error_response['message'] = 'Permission denied.'
        error_response['errors'].append('You do not have permission to perform this action.')
        
    elif isinstance(exc, NotFound):
        error_response['message'] = 'Resource not found.'
        error_response['errors'].append('The requested resource was not found.')
        
    elif isinstance(exc, MethodNotAllowed):
        error_response['message'] = 'Method not allowed.'
        error_response['errors'].append(f'Method {context["request"].method} not allowed.')
        
    elif isinstance(exc, Throttled):
        error_response['message'] = 'Request throttled.'
        error_response['errors'].append(
            f'Request was throttled. Expected available in {exc.wait} seconds.'
        )
        
    else:
        error_response['message'] = 'Error occurred.'
        error_response['errors'].append(str(exc))
    
    response.data = error_response
    return response