"""
VideoDB Sandbox Manager for Hackathon
Handles sandbox creation, lifecycle, and resource management.
"""

import logging
from typing import Optional, Dict, Any
from videodb import connect, SandboxTier, SandboxModel
from config import get_settings

logger = logging.getLogger(__name__)

# Global sandbox pool
_sandboxes: Dict[str, Any] = {}


class SandboxManager:
    """Manage VideoDB sandboxes for hackathon workloads."""
    
    def __init__(self):
        self.settings = get_settings()
        self.conn = None
        self.active_sandboxes = {}
    
    def initialize(self):
        """Initialize VideoDB connection."""
        try:
            self.conn = connect(api_key=self.settings.videodb_api_key)
            logger.info("VideoDB connection initialized for sandbox manager")
        except Exception as e:
            logger.error(f"Failed to initialize VideoDB: {e}")
            raise
    
    async def create_sandbox(
        self,
        tier: SandboxTier = SandboxTier.medium,
        idle_timeout: int = 600,
        name: str = "meridian-sandbox"
    ) -> str:
        """
        Create a sandbox for AI workloads.
        
        Args:
            tier: SandboxTier.small ($1/hr) or SandboxTier.medium ($3.50/hr)
            idle_timeout: Stop after N seconds of inactivity
            name: Sandbox name for tracking
        
        Returns:
            Sandbox ID
        """
        if not self.conn:
            raise RuntimeError("Sandbox manager not initialized")
        
        try:
            sandbox = self.conn.create_sandbox(
                tier=tier,
                idle_timeout=idle_timeout,
                name=name
            )
            
            sandbox_id = sandbox.id
            self.active_sandboxes[sandbox_id] = sandbox
            
            logger.info(f"Created sandbox {sandbox_id} (tier: {tier}, status: {sandbox.status})")
            
            return sandbox_id
        
        except Exception as e:
            logger.error(f"Failed to create sandbox: {e}")
            raise
    
    async def wait_for_sandbox(
        self,
        sandbox_id: str,
        timeout: int = 300,
        interval: int = 5
    ) -> bool:
        """
        Wait for sandbox to become active.
        
        Args:
            sandbox_id: Sandbox ID to wait for
            timeout: Max wait time in seconds
            interval: Check interval in seconds
        
        Returns:
            True if active, False if timeout
        """
        try:
            sandbox = self.active_sandboxes.get(sandbox_id)
            
            if not sandbox:
                sandbox = self.conn.get_sandbox(sandbox_id)
                self.active_sandboxes[sandbox_id] = sandbox
            
            sandbox.wait_for_ready(timeout=timeout, interval=interval)
            
            if sandbox.is_active:
                logger.info(f"Sandbox {sandbox_id} is active")
                return True
            else:
                logger.warning(f"Sandbox {sandbox_id} status: {sandbox.status}")
                return False
        
        except Exception as e:
            logger.error(f"Failed waiting for sandbox {sandbox_id}: {e}")
            raise
    
    async def stop_sandbox(self, sandbox_id: str) -> bool:
        """
        Stop a sandbox to conserve credits.
        
        Args:
            sandbox_id: Sandbox ID to stop
        
        Returns:
            True if stopped successfully
        """
        try:
            sandbox = self.active_sandboxes.get(sandbox_id)
            
            if not sandbox:
                sandbox = self.conn.get_sandbox(sandbox_id)
            
            sandbox.stop()
            sandbox.wait_for_stop(timeout=120)
            
            if sandbox_id in self.active_sandboxes:
                del self.active_sandboxes[sandbox_id]
            
            logger.info(f"Sandbox {sandbox_id} stopped")
            return True
        
        except Exception as e:
            logger.error(f"Failed to stop sandbox {sandbox_id}: {e}")
            raise
    
    async def list_sandboxes(self) -> list:
        """List all active sandboxes."""
        try:
            sandboxes = self.conn.list_sandboxes()
            return sandboxes
        except Exception as e:
            logger.error(f"Failed to list sandboxes: {e}")
            raise
    
    async def get_sandbox_status(self, sandbox_id: str) -> Dict[str, Any]:
        """Get sandbox status."""
        try:
            sandbox = self.active_sandboxes.get(sandbox_id)
            
            if not sandbox:
                sandbox = self.conn.get_sandbox(sandbox_id)
            
            sandbox.refresh()
            
            return {
                "id": sandbox.id,
                "status": sandbox.status,
                "is_active": sandbox.is_active,
                "tier": sandbox.tier,
                "name": sandbox.name
            }
        
        except Exception as e:
            logger.error(f"Failed to get sandbox status: {e}")
            raise


# Global instance
_sandbox_manager: Optional[SandboxManager] = None


def get_sandbox_manager() -> SandboxManager:
    """Get or create sandbox manager."""
    global _sandbox_manager
    
    if _sandbox_manager is None:
        _sandbox_manager = SandboxManager()
        _sandbox_manager.initialize()
    
    return _sandbox_manager


async def create_session_sandbox() -> str:
    """Create a sandbox for a session's AI workloads."""
    manager = get_sandbox_manager()
    
    sandbox_id = await manager.create_sandbox(
        tier=SandboxTier.medium,
        idle_timeout=900,  # 15 minutes
        name="meridian-session"
    )
    
    await manager.wait_for_sandbox(sandbox_id)
    
    return sandbox_id
