import logging
from typing import List, Dict, Any, Optional
from videodb import connect
from videodb.editor import Timeline, Track, Clip, VideoAsset, AudioAsset, ImageAsset, Fit
from videodb import SandboxModel, SceneExtractionType, IndexType, SearchType
from config import get_settings

logger = logging.getLogger(__name__)


class VideoDB:
    """Wrapper around VideoDB SDK with correct API signatures."""
    
    def __init__(self):
        self.settings = get_settings()
        self.conn = None
    
    def initialize(self):
        """Initialize VideoDB connection."""
        try:
            self.conn = connect(api_key=self.settings.videodb_api_key)
            logger.info("VideoDB connection initialized")
        except Exception as e:
            logger.error(f"Failed to initialize VideoDB: {e}")
            raise
    
    async def create_capture_session(self, end_user_id: str, capture_type: str = "transcript", metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a new capture session.
        
        Args:
            end_user_id: The end user identifier
            capture_type: Type of capture ("transcript" or "screen_recording")
            metadata: Optional metadata dict
        
        Returns:
            Session response with capture_session_id
        """
        if not self.conn:
            raise RuntimeError("VideoDB not initialized")
        
        callback_url = f"{self.settings.callback_base_url}/webhooks/capture"
        
        try:
            session = self.conn.create_capture_session(
                end_user_id=end_user_id,
                callback_url=callback_url,
                metadata=metadata or {"capture_type": capture_type}
            )
            
            # Convert CaptureSession object to dict
            session_dict = {
                "capture_session_id": session.id if hasattr(session, 'id') else str(session),
                "end_user_id": end_user_id,
                "capture_type": capture_type,
                "metadata": metadata or {}
            }
            
            logger.info(f"Created capture session: {session_dict['capture_session_id']}")
            return session_dict
        except Exception as e:
            logger.error(f"Failed to create capture session: {e}")
            raise
    
    async def generate_client_token(self, expires_in: int = 600) -> str:
        """
        Generate a client token for embedding capture widget.
        
        Args:
            expires_in: Token expiry in seconds
        
        Returns:
            Client token string
        """
        if not self.conn:
            raise RuntimeError("VideoDB not initialized")
        
        try:
            token = self.conn.generate_client_token(expires_in=expires_in)
            logger.info("Generated client token")
            return token
        except Exception as e:
            logger.error(f"Failed to generate client token: {e}")
            raise
    
    async def get_rtstream(self, rtstream_id: str) -> Dict[str, Any]:
        """
        Get RTStream details.
        
        Args:
            rtstream_id: The RTStream ID
        
        Returns:
            RTStream details
        """
        if not self.conn:
            raise RuntimeError("VideoDB not initialized")
        
        try:
            collection = self.conn.get_collection()
            rtstream = collection.get_rtstream(rtstream_id)
            logger.info(f"Retrieved RTStream: {rtstream_id}")
            return rtstream
        except Exception as e:
            logger.error(f"Failed to get RTStream {rtstream_id}: {e}")
            raise
    
    async def index_visuals(self, rtstream_id: str) -> List[Dict[str, Any]]:
        """
        Index visual frames from an RTStream.
        
        Args:
            rtstream_id: The RTStream ID
        
        Returns:
            List of indexed visuals with visual_index, timestamp, and description
        """
        if not self.conn:
            raise RuntimeError("VideoDB not initialized")
        
        try:
            collection = self.conn.get_collection()
            rtstream = collection.get_rtstream(rtstream_id)
            indexed_visuals = rtstream.index_visuals()
            
            logger.info(f"Indexed {len(indexed_visuals)} visuals from RTStream: {rtstream_id}")
            return indexed_visuals
        except Exception as e:
            logger.error(f"Failed to index visuals for RTStream {rtstream_id}: {e}")
            raise
    
    async def build_receipt_video(self, clip_specs: List[Dict[str, Any]], title: str = "Accountability Receipt") -> str:
        """
        Build a receipt video from clip specifications.
        
        Args:
            clip_specs: List of {"rtstream_id", "start_time", "end_time", "annotation"} dicts
            title: Video title
        
        Returns:
            Video ID
        """
        if not self.conn:
            raise RuntimeError("VideoDB not initialized")
        
        try:
            timeline = Timeline()
            
            for i, spec in enumerate(clip_specs):
                rtstream_id = spec.get("rtstream_id")
                start_time = spec.get("start_time", 0)
                end_time = spec.get("end_time")
                annotation = spec.get("annotation", "")
                
                # Get RTStream and create clip
                rtstream = self.conn.get_rtstream(rtstream_id)
                
                clip = Clip(
                    asset=rtstream,
                    start=start_time,
                    end=end_time
                )
                
                # Add to track
                track = Track(clips=[clip])
                timeline.add_track(track)
                
                # Add text annotation
                if annotation:
                    timeline.add_subtitle(
                        text=annotation,
                        start=start_time,
                        end=end_time or start_time + 5
                    )
            
            # Build video
            video = timeline.generate(title=title)
            video_id = video.id
            
            logger.info(f"Generated receipt video: {video_id}")
            return video_id
        except Exception as e:
            logger.error(f"Failed to build receipt video: {e}")
            raise
    
    async def get_video_url(self, video_id: str) -> str:
        """
        Get the public URL for a video.
        
        Args:
            video_id: The video ID
        
        Returns:
            Video URL
        """
        if not self.conn:
            raise RuntimeError("VideoDB not initialized")
        
        try:
            collection = self.conn.get_collection()
            video = collection.get_video(video_id)
            url = video.get_download_url()
            logger.info(f"Retrieved video URL: {video_id}")
            return url
        except Exception as e:
            logger.error(f"Failed to get video URL for {video_id}: {e}")
            raise
    
    # ===== SANDBOX-BACKED AI OPERATIONS (Hackathon) =====
    
    async def index_scenes_with_ai(
        self,
        video_id: str,
        prompt: str = "Describe the scene in detail",
        model_name: str = SandboxModel.GEMMA_4_31B,
        sandbox_id: Optional[str] = None
    ) -> str:
        """
        Index video scenes using VLM with sandbox compute.
        
        Args:
            video_id: Video to index
            prompt: Extraction prompt for the model
            model_name: Model to use (GEMMA_4_31B, GEMMA_4_26B, QWEN_9B, QWEN_27B)
            sandbox_id: Sandbox to run on
        
        Returns:
            Index ID
        """
        if not self.conn:
            raise RuntimeError("VideoDB not initialized")
        
        try:
            video = self.conn.get_video(video_id)
            
            index_id = video.index_scenes(
                extraction_type=SceneExtractionType.time_based,
                extraction_config={
                    "time": 10,
                    "select_frames": ["first"],
                    "frame_count": 1,
                },
                model_name=model_name,
                prompt=prompt,
                sandbox_id=sandbox_id
            )
            
            logger.info(f"Indexed scenes for video {video_id}, index: {index_id}")
            return index_id
        
        except Exception as e:
            logger.error(f"Failed to index scenes: {e}")
            raise
    
    async def index_rtstream_visuals_with_ai(
        self,
        rtstream_id: str,
        prompt: str = "Describe what is happening in the video",
        model_name: str = SandboxModel.GEMMA_4_31B,
        sandbox_id: Optional[str] = None
    ) -> str:
        """
        Index RTStream visuals using VLM with sandbox compute.
        
        Args:
            rtstream_id: RTStream to index
            prompt: Description prompt
            model_name: VLM to use
            sandbox_id: Sandbox ID
        
        Returns:
            Index ID
        """
        if not self.conn:
            raise RuntimeError("VideoDB not initialized")
        
        try:
            collection = self.conn.get_collection()
            rtstream = collection.get_rtstream(rtstream_id)
            
            visual_index = rtstream.index_visuals(
                prompt=prompt,
                batch_config={"type": "time", "value": 5, "frame_count": 3},
                model_name=model_name,
                sandbox_id=sandbox_id,
                name="meridian_visual_index"
            )
            
            logger.info(f"Indexed RTStream {rtstream_id} visuals, index: {visual_index.id}")
            return visual_index.id
        
        except Exception as e:
            logger.error(f"Failed to index RTStream visuals: {e}")
            raise
    
    async def generate_narration(
        self,
        text: str,
        voice_config: Optional[Dict[str, Any]] = None,
        sandbox_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate narration audio using OmniVoice.
        
        Args:
            text: Text to speak
            voice_config: Voice configuration
                - instructions: "female, calm, professional"
                - ref_audio: reference audio URL for cloning
                - ref_text: reference text for cloning
                - language: "en", "es", etc.
                - speed: 0.5-2.0
                - response_format: "wav", "mp3"
            sandbox_id: Sandbox ID
        
        Returns:
            {
                "audio_id": "...",
                "url": "...",
                "length": 12.5
            }
        """
        if not self.conn:
            raise RuntimeError("VideoDB not initialized")
        
        try:
            collection = self.conn.get_collection()
            
            job = collection.generate_voice(
                text=text,
                model_name=SandboxModel.OMNIVOICE,
                sandbox_id=sandbox_id,
                config=voice_config or {}
            )
            
            audio = job.wait(timeout=900, interval=5)
            
            logger.info(f"Generated narration audio: {audio.id}")
            
            return {
                "audio_id": audio.id,
                "url": audio.get_download_url(),
                "length": float(audio.length)
            }
        
        except Exception as e:
            logger.error(f"Failed to generate narration: {e}")
            raise
    
    async def generate_image(
        self,
        prompt: str,
        image_config: Optional[Dict[str, Any]] = None,
        sandbox_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate image using FLUX.
        
        Args:
            prompt: Image description
            image_config: FLUX configuration
                - size: "1024x1024", "1280x720", "1024x1536"
                - num_inference_steps: 28-50
                - guidance_scale: 4.0-7.5
                - negative_prompt: what to avoid
            sandbox_id: Sandbox ID
        
        Returns:
            {
                "image_id": "...",
                "url": "...",
                "width": 1024,
                "height": 1024
            }
        """
        if not self.conn:
            raise RuntimeError("VideoDB not initialized")
        
        try:
            collection = self.conn.get_collection()
            
            job = collection.generate_image(
                prompt=prompt,
                model_name=SandboxModel.FLUX,
                sandbox_id=sandbox_id,
                config=image_config or {}
            )
            
            image = job.wait(timeout=900, interval=5)
            
            logger.info(f"Generated image: {image.id}")
            
            return {
                "image_id": image.id,
                "url": image.get_download_url(),
                "width": image.width,
                "height": image.height
            }
        
        except Exception as e:
            logger.error(f"Failed to generate image: {e}")
            raise
    
    async def build_receipt_video_with_assets(
        self,
        clip_specs: List[Dict[str, Any]],
        narration_text: Optional[str] = None,
        background_image_id: Optional[str] = None,
        title: str = "Accountability Receipt",
        sandbox_id: Optional[str] = None
    ) -> str:
        """
        Build premium accountability receipt with AI-generated narration and imagery.
        
        Args:
            clip_specs: List of {"rtstream_id", "start_time", "end_time", "annotation"}
            narration_text: Text to generate as narration
            background_image_id: Background image ID (from FLUX generation)
            title: Video title
            sandbox_id: Sandbox for generating narration
        
        Returns:
            Video ID
        """
        if not self.conn:
            raise RuntimeError("VideoDB not initialized")
        
        try:
            timeline = Timeline()
            
            # Add video clips
            for spec in clip_specs:
                rtstream_id = spec.get("rtstream_id")
                start_time = spec.get("start_time", 0)
                end_time = spec.get("end_time")
                annotation = spec.get("annotation", "")
                
                rtstream = self.conn.get_rtstream(rtstream_id)
                
                clip = Clip(
                    asset=rtstream,
                    start=start_time,
                    end=end_time
                )
                
                track = Track(clips=[clip])
                timeline.add_track(track)
                
                if annotation:
                    timeline.add_subtitle(
                        text=annotation,
                        start=start_time,
                        end=end_time or start_time + 5
                    )
            
            # Generate and add narration if requested
            if narration_text and sandbox_id:
                narration = await self.generate_narration(
                    text=narration_text,
                    voice_config={
                        "instructions": "professional, clear, authoritative",
                        "response_format": "wav"
                    },
                    sandbox_id=sandbox_id
                )
                
                # Add audio track
                audio_track = Track()
                audio_track.add_clip(
                    0,
                    Clip(
                        asset=AudioAsset(id=narration["audio_id"]),
                        duration=narration["length"]
                    )
                )
                timeline.add_track(audio_track)
            
            # Build video
            video = timeline.generate(title=title)
            video_id = video.id
            
            logger.info(f"Generated premium receipt video: {video_id}")
            return video_id
        
        except Exception as e:
            logger.error(f"Failed to build premium receipt video: {e}")
            raise
    
    async def _extract_visual_descriptions(
        self,
        visual_index_id: str,
        rtstream_id: str
    ) -> List[Dict[str, Any]]:
        """
        Extract structured descriptions from VLM visual index.
        
        Args:
            visual_index_id: Index ID from VLM indexing
            rtstream_id: RTStream ID
        
        Returns:
            List of visual descriptions with timestamps
        """
        if not self.conn:
            raise RuntimeError("VideoDB not initialized")
        
        try:
            collection = self.conn.get_collection()
            rtstream = collection.get_rtstream(rtstream_id)
            
            # Get indexed visuals
            visuals = rtstream.get_visual_index(visual_index_id)
            
            visual_descriptions = []
            for idx, visual in enumerate(visuals or []):
                visual_descriptions.append({
                    "visual_index": idx,
                    "description": visual.get("description", ""),
                    "timestamp": visual.get("timestamp", idx * 5),
                    "confidence": visual.get("confidence", 0.8)
                })
            
            logger.info(f"Extracted {len(visual_descriptions)} visual descriptions")
            return visual_descriptions
        
        except Exception as e:
            logger.warning(f"Failed to extract visual descriptions: {e}")
            return []


# Global instance
_videodb_instance: Optional[VideoDB] = None


def get_videodb() -> VideoDB:
    """Get or create VideoDB instance."""
    global _videodb_instance
    
    if _videodb_instance is None:
        _videodb_instance = VideoDB()
        _videodb_instance.initialize()
    
    return _videodb_instance
