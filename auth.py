"""
Authentication module for Sentinel Hub API
Handles OAuth2 token management and authentication
"""

import os
import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class SentinelHubAuth:
    """Handles authentication with Sentinel Hub API using OAuth2"""
    
    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None):
        """
        Initialize authentication handler
        
        Args:
            client_id: Sentinel Hub client ID (from environment if None)
            client_secret: Sentinel Hub client secret (from environment if None)
        """
        self.client_id = client_id or os.environ.get('SENTINEL_HUB_CLIENT_ID')
        self.client_secret = client_secret or os.environ.get('SENTINEL_HUB_CLIENT_SECRET')
        self.token_url = "https://services.sentinel-hub.com/oauth/token"
        self.access_token = None
        self.token_expires_in = 0
        
        if not self.client_id or not self.client_secret:
            logger.warning("Sentinel Hub credentials not found in environment variables")
    
    def get_access_token(self) -> Optional[str]:
        """
        Get a valid access token, refreshing if necessary
        
        Returns:
            Valid access token string or None if authentication fails
        """
        if not self.client_id or not self.client_secret:
            logger.error("Missing Sentinel Hub credentials")
            return None
        
        try:
            # Request new token using client credentials flow
            response = requests.post(
                self.token_url,
                data={
                    'grant_type': 'client_credentials',
                    'client_id': self.client_id,
                    'client_secret': self.client_secret
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get('access_token')
                self.token_expires_in = token_data.get('expires_in', 3600)
                logger.info("Successfully obtained Sentinel Hub access token")
                return self.access_token
            else:
                logger.error(f"Failed to get access token: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error requesting access token: {e}")
            return None
    
    def is_authenticated(self) -> bool:
        """
        Check if we have valid credentials configured
        
        Returns:
            True if credentials are available, False otherwise
        """
        return bool(self.client_id and self.client_secret)