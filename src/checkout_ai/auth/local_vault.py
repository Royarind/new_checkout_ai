"""
Local Credential Management for Checkout AI
Stores user credentials securely on local machine using OS Keychain
"""
import keyring
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class LocalCredentialManager:
    """Manages credentials on user's local machine using OS Keychain"""
    
    SERVICE_NAME = "checkout_ai"
    
    def __init__(self, user_home: Path = None):
        """
        Initialize credential manager
        
        Args:
            user_home: User's home directory (defaults to Path.home())
        """
        self.user_home = user_home or Path.home()
        self.session_dir = self.user_home / '.checkout_ai' / 'sessions'
        self.session_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Credential manager initialized. Session dir: {self.session_dir}")
    
    # === CREDENTIAL STORAGE (OS Keychain) ===
    
    def save_credential(self, site: str, username: str, password: str) -> bool:
        """
        Save login credentials to OS Keychain
        
        Args:
            site: Site identifier (e.g., 'myntra', 'flipkart')
            username: Username/email/phone
            password: Password
            
        Returns:
            True if saved successfully
        """
        try:
            service_name = f"{self.SERVICE_NAME}_{site}"
            keyring.set_password(service_name, username, password)
            logger.info(f"✅ Saved credentials for {site} (user: {username})")
            return True
        except Exception as e:
            logger.error(f"Failed to save credentials for {site}: {e}")
            return False
    
    def get_credential(self, site: str, username: str) -> Optional[str]:
        """
        Retrieve password from OS Keychain
        
        Args:
            site: Site identifier
            username: Username to retrieve password for
            
        Returns:
            Password if found, None otherwise
        """
        try:
            service_name = f"{self.SERVICE_NAME}_{site}"
            password = keyring.get_password(service_name, username)
            
            if password:
                logger.info(f"✅ Retrieved credentials for {site} (user: {username})")
            else:
                logger.warning(f"No credentials found for {site} (user: {username})")
            
            return password
        except Exception as e:
            logger.error(f"Failed to retrieve credentials for {site}: {e}")
            return None
    
    def delete_credential(self, site: str, username: str) -> bool:
        """
        Delete credentials from OS Keychain
        
        Args:
            site: Site identifier
            username: Username
            
        Returns:
            True if deleted successfully
        """
        try:
            service_name = f"{self.SERVICE_NAME}_{site}"
            keyring.delete_password(service_name, username)
            logger.info(f"🗑️ Deleted credentials for {site} (user: {username})")
            return True
        except Exception as e:
            logger.error(f"Failed to delete credentials for {site}: {e}")
            return False
    
    def list_saved_sites(self) -> list:
        """
        List all sites with saved credentials
        
        Note: This is limited by keyring backend capabilities
        
        Returns:
            List of site identifiers
        """
        # This is a best-effort implementation
        # Some keyring backends don't support listing
        # For now, we maintain a separate index file
        index_file = self.session_dir / 'credential_index.json'
        
        if index_file.exists():
            try:
                with open(index_file, 'r') as f:
                    return json.load(f).get('sites', [])
            except:
                return []
        return []
    
    def _update_credential_index(self, site: str, username: str):
        """Update index of saved credentials"""
        index_file = self.session_dir / 'credential_index.json'
        
        index_data = {'sites': []}
        if index_file.exists():
            try:
                with open(index_file, 'r') as f:
                    index_data = json.load(f)
            except:
                pass
        
        # Add site if not already in index
        site_entry = {'site': site, 'username': username}
        if site_entry not in index_data.get('sites', []):
            index_data.setdefault('sites', []).append(site_entry)
        
        with open(index_file, 'w') as f:
            json.dump(index_data, f, indent=2)
    
    # === SESSION STORAGE (Local Files) ===
    
    async def save_session(self, user_id: str, site: str, page) -> bool:
        """
        Save session cookies after successful login
        
        Args:
            user_id: User identifier
            site: Site identifier
            page: Playwright Page object
            
        Returns:
            True if saved successfully
        """
        try:
            cookies = await page.context.cookies()
            
            # Try to get localStorage too
            try:
                local_storage = await page.evaluate("() => JSON.stringify(localStorage)")
            except:
                local_storage = "{}"
            
            session_data = {
                'cookies': [
                    {
                        'name': c['name'],
                        'value': c['value'],
                        'domain': c['domain'],
                        'path': c['path'],
                        'expires': c.get('expires', -1),
                        'httpOnly': c.get('httpOnly', False),
                        'secure': c.get('secure', False),
                        'sameSite': c.get('sameSite', 'Lax')
                    }
                    for c in cookies
                ],
                'localStorage': local_storage,
                'saved_at': datetime.now().isoformat(),
                'expires_at': (datetime.now() + timedelta(days=30)).isoformat()
            }
            
            session_file = self.session_dir / f"{site}_{user_id}.json"
            with open(session_file, 'w') as f:
                json.dump(session_data, f, indent=2)
            
            logger.info(f"💾 Saved session for {site} (user: {user_id})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save session for {site}: {e}")
            return False
    
    async def restore_session(self, user_id: str, site: str, page) -> bool:
        """
        Restore session from saved cookies
        
        Args:
            user_id: User identifier
            site: Site identifier
            page: Playwright Page object
            
        Returns:
            True if session restored successfully
        """
        try:
            session_file = self.session_dir / f"{site}_{user_id}.json"
            
            if not session_file.exists():
                logger.info(f"No saved session for {site} (user: {user_id})")
                return False
            
            with open(session_file, 'r') as f:
                session_data = json.load(f)
            
            # Check expiry
            expires_at = datetime.fromisoformat(session_data['expires_at'])
            if datetime.now() > expires_at:
                logger.warning(f"Session expired for {site} (user: {user_id})")
                session_file.unlink()  # Delete expired session
                return False
            
            # Restore cookies
            await page.context.add_cookies(session_data['cookies'])
            
            # Restore localStorage
            try:
                await page.evaluate(f"localStorage = {session_data['localStorage']}")
            except:
                pass
            
            logger.info(f"✅ Restored session for {site} (user: {user_id})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore session for {site}: {e}")
            return False
    
    def delete_session(self, user_id: str, site: str) -> bool:
        """Delete saved session"""
        try:
            session_file = self.session_dir / f"{site}_{user_id}.json"
            if session_file.exists():
                session_file.unlink()
                logger.info(f"🗑️ Deleted session for {site} (user: {user_id})")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete session for {site}: {e}")
            return False


# Singleton instance
_credential_manager = None

def get_credential_manager() -> LocalCredentialManager:
    """Get or create singleton credential manager"""
    global _credential_manager
    if _credential_manager is None:
        _credential_manager = LocalCredentialManager()
    return _credential_manager
