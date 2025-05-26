# utils/ai_matcher.py
from openai import OpenAI
from config.config import FORM_HISTORY_PATH
from utils.api_key_manager import get_api_key_manager
from collections import defaultdict, Counter
import re
import google.generativeai as genai
import json
import logging
from typing import Dict, List, Optional, Any, Union
from .field_matcher import EnhancedFieldMatcher
import hashlib
from sentence_transformers import SentenceTransformer
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class AIFieldMatcher:
    def __init__(self, form_history_path: str = FORM_HISTORY_PATH):
        self.field_matcher = EnhancedFieldMatcher(form_history_path)
        self.context_cache = {}
        self.suggestion_cache = {}
        self._openai_client = None
        self._gemini_client = None
        self._client = None
        self.form_context_analysis = {}
        self.field_relationships = defaultdict(list)
        self.field_name_mapping = {}
        self.similar_fields_cache = {}
        self.sbert_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.last_api_call = datetime.min
        self.api_call_count = 0
        self.MAX_API_CALLS_PER_MINUTE = 30
        self.current_provider = None
        self.provider_priority = ["openai", "gemini"]
        self.gemini_model_name = "gemini-2.0-flash"
        
        # Initialize providers first
        self._initialize_providers()
        
        # Then initialize other components
        self._initialize_components()
        
        # Verify initialization
        self._verify_initialization()

    def _initialize_providers(self):
        """Initialize available AI providers with proper error handling"""
        api_key_manager = get_api_key_manager()
        self.current_provider = None
        
        # Initialize API key manager if needed
        try:
            if not hasattr(api_key_manager, '_initialized') or not api_key_manager._initialized:
                api_key_manager._initialize()
        except Exception as e:
            logger.error(f"API key manager initialization failed: {str(e)}")

        # Try each provider in priority order
        for provider in self.provider_priority:
            try:
                if provider == "openai":
                    client = api_key_manager._get_openai_client()
                    print
                    if client is not None:
                        # Test the OpenAI connection
                        try:
                            if client.models.list():  # Test connection
                                self._openai_client = client
                                self.current_provider = "openai"
                                logger.info("OpenAI provider initialized and verified")
                                break
                        except Exception as e:
                            logger.warning(f"OpenAI connection test failed: {str(e)}")
                            continue
                            
                elif provider == "gemini":
                    client = api_key_manager._get_gemini_client()
                    if client is not None:
                        # Test the Gemini connection
                        try:
                            response = client.generate_content("Test connection") 
                            if response.text:
                                self._gemini_client = client
                                self.current_provider = "gemini"
                                logger.info("Gemini provider initialized and verified")
                                break
                        except Exception as e:
                            logger.warning(f"Gemini connection test failed: {str(e)}")
                            continue
                            
            except Exception as e:
                logger.error(f"Failed to initialize {provider}: {str(e)}")
                continue
                
        # If still no provider, try direct initialization from environment
        if self.current_provider is None:
            self._try_direct_initialization()
            
        # Final check
        if self.current_provider is None:
            logger.error("No working AI providers available - falling back to local mode")
    def _try_direct_initialization(self):
        """Try to initialize clients directly from environment variables"""
        import os
        try:
            # Try OpenAI first
            openai_key = os.getenv('OPENAI_API_KEY')
            if openai_key:
                self._openai_client = OpenAI(api_key=openai_key)
                self.current_provider = "openai"
                logger.info("Direct OpenAI initialization from env succeeded")
                return
                
            # Then try Gemini
            gemini_key = os.getenv('GEMINI_API_KEY')
            if gemini_key:
                genai.configure(api_key=gemini_key)
                self._gemini_client = genai.GenerativeModel('gemini-pro')
                self.current_provider = "gemini"
                logger.info("Direct Gemini initialization from env succeeded")
                return
                
        except Exception as e:
            logger.error(f"Direct initialization failed: {str(e)}")
    def _verify_initialization(self):
            """Verify that critical components are initialized"""
            if self.current_provider is None:
                logger.warning("Running in local-only mode - no AI providers available")
                
            # Verify field matcher initialization
            if not hasattr(self.field_matcher, 'form_history'):
                logger.error("Field matcher initialization failed - form history not loaded")

    def _initialize_components(self):
        """Initialize all internal components"""
        try:
            self.field_matcher._build_models()
            self.field_matcher._load_user_preferences()
            self._analyze_field_relationships()
            self._build_field_name_mapping()
            logger.info("All components initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing components: {str(e)}")
            raise RuntimeError(f"Initialization failed: {str(e)}")

    def _build_field_name_mapping(self):
        """Build mapping between field name variants with validation"""
        try:
            if not hasattr(self.field_matcher, 'form_history'):
                raise AttributeError("Form history not loaded")
                
            field_variants = defaultdict(set)
            
            for form in self.field_matcher.form_history:
                if not isinstance(form, dict):
                    continue
                    
                form_data = form.get('form_data', {})
                if not isinstance(form_data, dict):
                    continue
                    
                for field_name in form_data.keys():
                    if not isinstance(field_name, str):
                        continue
                        
                    normalized_name = self._normalize_field_name(field_name)
                    if normalized_name:
                        field_variants[normalized_name].add(field_name)
            
            # Build two-way mapping
            for norm_name, variants in field_variants.items():
                variants_list = list(variants)
                for variant in variants_list:
                    self.field_name_mapping[variant] = variants_list
            
            logger.info(f"Built field name mapping with {len(self.field_name_mapping)} entries")
            return True
            
        except Exception as e:
            logger.error(f"Error building field name mapping: {str(e)}")
            return False

    def _normalize_field_name(self, field_name: str) -> str:
        """Normalize field name for comparison with validation"""
        if not isinstance(field_name, str) or not field_name.strip():
            return ""
        
        try:
            # Remove special chars and common field words
            normalized = re.sub(r'[^\w\s]', '', field_name.lower())
            normalized = re.sub(r'\b(field|input|text|form|data)\b', '', normalized)
            return re.sub(r'\s+', ' ', normalized).strip()
        except Exception as e:
            logger.warning(f"Error normalizing field name '{field_name}': {str(e)}")
            return field_name.lower().strip()

    def _analyze_field_relationships(self):
        """Analyze relationships between fields with proper error handling"""
        try:
            if not hasattr(self.field_matcher, 'form_history'):
                raise AttributeError("Form history not loaded")
                
            field_co_occurrence = defaultdict(lambda: defaultdict(int))
            processed_forms = 0
            
            for form in self.field_matcher.form_history:
                if not isinstance(form, dict):
                    continue
                    
                form_data = form.get('form_data', {})
                if not isinstance(form_data, dict):
                    continue
                    
                fields = [f for f in form_data.keys() 
                         if isinstance(f, str) and f not in ['form_id', 'document_name', 'form_type']]
                processed_forms += 1
                
                # Update co-occurrence counts
                for i, field1 in enumerate(fields):
                    for field2 in fields[i+1:]:
                        field_co_occurrence[field1][field2] += 1
                        field_co_occurrence[field2][field1] += 1
            
            # Store top 5 related fields
            for field, related_fields in field_co_occurrence.items():
                sorted_related = sorted(related_fields.items(), 
                                      key=lambda x: x[1], 
                                      reverse=True)
                self.field_relationships[field] = [f[0] for f in sorted_related[:5]]
                
            logger.info(f"Analyzed relationships for {len(self.field_relationships)} fields from {processed_forms} forms")
            return True
            
        except Exception as e:
            logger.error(f"Error analyzing field relationships: {str(e)}")
            return False

    @property
    def client(self):
        if self._client is None:
            api_key_manager = get_api_key_manager()
            self._client = api_key_manager.get_client()
            if self._client is None:
                raise RuntimeError("Failed to initialize OpenAI client. Check API key configuration.")
        return self._client
    def _switch_provider(self):
        """Safely switch to the next available provider"""
        if not self.current_provider:
            self._initialize_providers()
            return
            
        current_index = self.provider_priority.index(self.current_provider)
        
        for next_index in range(current_index + 1, len(self.provider_priority)):
            next_provider = self.provider_priority[next_index]
            try:
                if next_provider == "openai" and self._openai_client is not None:
                    self.current_provider = next_provider
                    logger.info("Switched to OpenAI provider")
                    return
                    
                elif next_provider == "gemini" and self._gemini_client is not None:
                    self.current_provider = next_provider
                    logger.info("Switched to Gemini provider")
                    return
                    
            except Exception as e:
                logger.error(f"Error switching to {next_provider}: {str(e)}")
                continue
                
        logger.error("No available AI providers could be initialized")
        self.current_provider = None

    def _rate_limit_check(self):
        """Enforce API rate limiting with time window"""
        now = datetime.now()
        time_since_last = now - self.last_api_call
        
        # Reset counter if more than 1 minute has passed
        if time_since_last > timedelta(minutes=1):
            self.last_api_call = now
            self.api_call_count = 1
            return
            
        # Check if we've exceeded the limit
        if self.api_call_count >= self.MAX_API_CALLS_PER_MINUTE:
            time_to_wait = timedelta(minutes=1) - time_since_last
            logger.warning(f"Rate limit exceeded. Waiting {time_to_wait.total_seconds()} seconds")
            raise RuntimeError(f"API rate limit exceeded. Please wait {time_to_wait.seconds} seconds")
            
        self.api_call_count += 1
    def _call_openai_api(self, prompt: str, system_message: str, is_json: bool, max_tokens: int):
        """Handle OpenAI API calls"""
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ]
        
        response = self._openai_client.chat.completions.create(
            model="gpt-4-1106-preview",
            messages=messages,
            temperature=0.5,
            max_tokens=max_tokens,
            response_format="json" if is_json else "text"

        )
        message_content = response.choices[0].message.content
        if message_content is None:
            raise ValueError("No content received from OpenAI API.")
        return message_content.strip()
    def _call_gemini_api(self, prompt: str, system_message: str, max_tokens: int):
        """Handle Gemini API calls"""
        model = genai.GenerativeModel(self.gemini_model_name)
        response = model.generate_content(
            f"{system_message}\n\n{prompt}",
            generation_config={
                "temperature": 0.3,
                "max_output_tokens": max_tokens,
            }
        )
        return response.text
    def _call_ai_api(self, prompt: str, system_message: str, is_json: bool = False, max_tokens: int = 200):
        """Call AI API with robust error handling"""
        if not self.client:
            logger.error("No AI client available for API call")
            raise RuntimeError("No AI providers available")
            
        try:
            self._rate_limit_check()
            
            if self.current_provider == "openai":
                try:
                    response = self._call_openai_api(prompt, system_message, is_json, max_tokens)
                    if response is None:
                        raise ValueError("OpenAI returned None response")
                    return response
                except Exception as e:
                    logger.error(f"OpenAI API call failed: {str(e)}")
                    # Mark OpenAI as unavailable
                    self._openai_client = None
                    self._switch_provider()
                    
            if self.current_provider == "gemini":
                try:
                    response = self._call_gemini_api(prompt, system_message, max_tokens)
                    if response is None:
                        raise ValueError("Gemini returned None response")
                    return response
                except Exception as e:
                    logger.error(f"Gemini API call failed: {str(e)}")
                    # Mark Gemini as unavailable
                    self._gemini_client = None
                    self._switch_provider()
                    
            # If we get here, all providers failed
            raise RuntimeError("All AI providers failed")
            
        except Exception as e:
            logger.error(f"API call completely failed: {str(e)}")
            raise RuntimeError(f"AI service unavailable: {str(e)}")

    def _generate_cache_key(self, *args) -> str:
        """Generate consistent cache key from multiple inputs"""
        key_string = "|".join(str(arg) for arg in args)
        return hashlib.sha256(key_string.encode('utf-8')).hexdigest()
    def _extract_context_locally(self, form_text: str) -> str:
        """Local fallback for context extraction"""
        # Implement basic regex-based extraction
        patterns = {
            'purpose': r'(Mục đích|Purpose):?\s*(.+?)\n',
            'form_type': r'(Loại|Type)\s*(biểu mẫu|form):?\s*(.+?)\n'
        }
        
        context = {}
        for key, pattern in patterns.items():
            match = re.search(pattern, form_text, re.IGNORECASE)
            if match:
                context[key] = match.group(2 if key == 'purpose' else 3).strip()
                
        return json.dumps(context, ensure_ascii=False) if context else "No context extracted"
    def _extract_context_with_ai(self, form_text: str) -> str:
        """Extract form context using AI with proper error handling and caching"""
        cache_key = self._generate_cache_key("context_extraction", form_text)
        if cache_key in self.context_cache:
            return self.context_cache[cache_key]
        
        try:
            # Prepare the prompt for AI
            prompt = f"""Analyze this form text and extract key context information in JSON format:
    {form_text[:5000]}  # Limit to first 5000 chars to avoid token limits

    Respond with JSON containing:
    - "form_purpose": Main purpose of the form
    - "form_type": Type/category of form
    - "key_fields": List of important fields
    - "target_audience": Who the form is for
    - "form_structure": Brief description of sections"""
            
            # Call AI API with proper error handling
            response = self._call_ai_api(
                prompt=prompt,
                system_message="You are a form analysis expert. Extract key context from form text.",
                is_json=True,
                max_tokens=300
            )
            
            # Ensure we got a response
            if response is None:
                raise ValueError("AI API returned None response")
            
            # Parse and validate the response
            try:
                context_data = json.loads(response)
                if not isinstance(context_data, dict):
                    raise ValueError("Invalid response format")
                    
                # Ensure required fields exist
                context_data.setdefault("form_purpose", "Unknown")
                context_data.setdefault("form_type", "General")
                context_data.setdefault("key_fields", [])
                context_data.setdefault("target_audience", "General")
                context_data.setdefault("form_structure", "Standard")
                
                # Cache the result
                self.context_cache[cache_key] = json.dumps(context_data, ensure_ascii=False)
                return self.context_cache[cache_key]
                
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Failed to parse AI context response: {str(e)}")
                return self._fallback_context_extraction(form_text)
                
        except Exception as e:
            logger.error(f"AI context extraction failed: {str(e)}")
            return self._extract_context_locally(form_text)
    def extract_context_from_form_text(self, form_text: str) -> str:
        """Extract context with proper fallback to local methods"""
        try:
            # First try AI extraction if available
            if self.client:
                return self._extract_context_with_ai(form_text)
                
            # Fallback to local extraction
            return self._extract_context_locally(form_text)
            
        except Exception as e:
            logger.error(f"Context extraction completely failed: {str(e)}")
            return ""

    def _fallback_context_extraction(self, form_text: str) -> str:
        """Fallback method for context extraction when AI fails"""
        # Simple regex-based extraction
        patterns = {
            "purpose": r"(mục đích|purpose):?\s*(.+?)\n",
            "target": r"(đối tượng|dành cho|target):?\s*(.+?)\n",
            "form_type": r"(loại|type)\s*(biểu mẫu|form):?\s*(.+?)\n"
        }
        
        context = {}
        for key, pattern in patterns.items():
            match = re.search(pattern, form_text, re.IGNORECASE)
            if match:
                context[key] = match.group(2 if key == "purpose" else -1).strip()
                
        return "\n".join(f"- {k}: {v}" for k, v in context.items()) if context else "No context extracted"

    def _enhance_context_analysis(self, form_text: str, context: str) -> Dict:
        """Enhanced context analysis with embeddings"""
        cache_key = self._generate_cache_key("enhanced_context", form_text)
        if cache_key in self.context_cache:
            return self.context_cache[cache_key]
            
        try:
            # Generate embeddings
            embeddings = self.sbert_model.encode([form_text, context])
            form_embedding, context_embedding = embeddings[0], embeddings[1]
            
            # Structure analysis prompt
            structure_prompt = f"""Analyze this form structure and respond with JSON:
{form_text[:2000]}

Response JSON format:
{{
  "form_type": "Job Application",
  "sections": ["Personal Info", "Work Experience", "Education"],
  "field_relationships": "Position relates to company and duration",
  "field_importance": {{
    "Name": "High",
    "Position": "High",
    "Company": "Medium",
    "Duration": "Medium"
  }},
  "field_extraction": {{
    "Company": "Example Company",
    "Position": "Office",
    "Location": "Commercial",
    "Start Date": "27/09/2003"
  }}
}}"""
            
            response = self._call_ai_api(
                prompt=structure_prompt,
                system_message="You are a form structure analysis expert.",
                is_json=True,
                max_tokens=300
            )
            
            analysis = json.loads(response)
            analysis.update({
                "form_embedding": form_embedding.tolist(),
                "context_embedding": context_embedding.tolist()
            })
            
            self.context_cache[cache_key] = analysis
            return analysis
            
        except Exception as e:
            logger.error(f"Enhanced context analysis failed: {str(e)}")
            return {}

    def _extract_key_fields(self, form_text: str) -> str:
        """Extract key fields using field matcher with validation"""
        if not form_text or not isinstance(form_text, str):
            return ""
            
        try:
            fields = self.field_matcher.find_most_similar_field(form_text, top_n=5)
            if not fields:
                return ""
                
            return "\n".join([f"- {field[0]} (confidence: {field[1]:.2f})" for field in fields])
        except Exception as e:
            logger.error(f"Key field extraction failed: {str(e)}")
            return ""

    def find_similar_fields(self, field_name: str, threshold: float = 0.6, max_results: int = 5) -> List[str]:
        """Find similar fields with caching and validation"""
        if not field_name or not isinstance(field_name, str):
            return []
            
        cache_key = self._generate_cache_key("similar_fields", field_name, threshold, max_results)
        if cache_key in self.similar_fields_cache:
            return self.similar_fields_cache[cache_key]
            
        try:
            # First check name mapping
            if field_name in self.field_name_mapping:
                similar_fields = self.field_name_mapping[field_name]
                if similar_fields:
                    result = similar_fields[:max_results]
                    self.similar_fields_cache[cache_key] = result
                    return result
                    
            # Fall back to field matcher
            similar_fields = [f[0] for f in 
                            self.field_matcher.find_most_similar_field(field_name, top_n=max_results) 
                            if f[1] >= threshold]
                            
            self.similar_fields_cache[cache_key] = similar_fields
            return similar_fields
            
        except Exception as e:
            logger.error(f"Similar fields lookup failed: {str(e)}")
            return []

    def generate_suggestions(
        self,
        field_name: str,
        historical_values: List[str],
        context: Optional[str] = None,
        form_type: Optional[str] = None,
        related_fields_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Generate smart suggestions with provider-specific optimization"""
        if not field_name or not isinstance(historical_values, list):
            return {"suggestions": [], "default": "", "reason": "Invalid input"}
            
        cache_key = self._generate_cache_key(
            "suggestions", 
            field_name, 
            tuple(historical_values), 
            context, 
            form_type, 
            json.dumps(related_fields_data, sort_keys=True) if related_fields_data else ""
        )
        
        if cache_key in self.suggestion_cache:
            return self.suggestion_cache[cache_key]
            
        try:
            if self.current_provider == "gemini":
                return self._generate_with_gemini(field_name, historical_values, context, form_type, related_fields_data)
            else:
                return self._generate_with_openai(field_name, historical_values, context, form_type, related_fields_data)
                
        except Exception as e:
            logger.error(f"Suggestion generation failed: {str(e)}")
            return self._generate_local_suggestions(field_name, historical_values)
    def _generate_local_suggestions(self, field_name: str, historical_values: List[str]) -> Dict[str, Any]:
        """Generate simple suggestions locally when AI services are unavailable"""
        if not historical_values:
            return {"suggestions": [], "default": "", "reason": "No historical data available"}
        
        # Simple frequency-based suggestions
        counter = Counter(historical_values)
        most_common = counter.most_common(2)
        
        suggestions = [
            {"text": value, "reason": f"Frequently used ({count} times)"}
            for value, count in most_common
        ]
        
        return {
            "suggestions": suggestions,
            "default": most_common[0][0] if most_common else "",
            "reason": "Generated from local frequency analysis"
        }
    def _parse_suggestion_response(self, content: str) -> Dict[str, Any]:
        """Robust parsing of AI suggestion response"""
        if content is None:
            logger.warning("Received None content in suggestion response")
            return {
                "suggestions": [],
                "default": "",
                "reason": "No response from AI service"
            }
        
        try:
            # First try direct JSON parse
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                # Try extracting JSON from markdown code block
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(1))
                else:
                    # Try to find any JSON-like structure
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        result = json.loads(json_match.group(0))
                    else:
                        raise ValueError("No valid JSON found in response")
            
            # Validate the result structure
            if not isinstance(result, dict):
                raise ValueError("Response is not a JSON object")
                
            return {
                "suggestions": result.get("suggestions", [])[:3],
                "default": result.get("default", ""),
                "reason": result.get("reason", "No reason provided")
            }
            
        except Exception as e:
            logger.error(f"Failed to parse suggestion response: {str(e)}")
            return {
                "suggestions": [],
                "default": "",
                "reason": f"Error parsing response: {str(e)}"
            }
    def _generate_with_gemini(
        self,
        field_name: str,
        historical_values: List[str],
        context: Optional[str],
        form_type: Optional[str],
        related_fields_data: Optional[Dict]
    ) -> Dict[str, Any]:
        """Generate suggestions optimized for Gemini"""
        prompt = (
            f"For field '{field_name}' in {form_type if form_type else 'a form'}, "
            f"based on these historical values:\n{', '.join(historical_values[:5])}\n\n"
            "Provide 2-3 best suggestions in JSON format:\n"
            "{\"suggestions\": [{\"text\": \"...\", \"reason\": \"...\"}], \"default\": \"...\"}"
        )
        
        if context:
            prompt += f"\nContext: {context[:200]}"
            
        if related_fields_data:
            prompt += f"\nRelated fields data: {json.dumps(related_fields_data, ensure_ascii=False)[:200]}"
            
        response = self._call_ai_api(
            prompt=prompt,
            system_message="You are a professional form filling assistant.",
            is_json=True,
            max_tokens=250
        )
        
        result = self._parse_suggestion_response(response)
        return result
    def _get_related_fields(self, field_name: str, similar_fields: List[str], related_data: Optional[Dict]) -> str:
            """Get information about related fields"""
            related_fields = self.field_relationships.get(field_name, [])
            if not related_fields and similar_fields:
                for similar_field in similar_fields:
                    if similar_field in self.field_relationships:
                        related_fields = self.field_relationships[similar_field]
                        break
            
            if not related_fields or not related_data:
                return ""
                
            related_info = []
            for rel_field in related_fields[:3]:
                if rel_field in related_data:
                    related_info.append(f"{rel_field}: {related_data[rel_field]}")
            return "\nRelated fields:\n- " + "\n- ".join(related_info) if related_info else ""
    def _build_optimized_prompt(
        self,
        field_name: str,
        similar_fields: List[str],
        historical_values: List[str],
        context: Optional[str],
        related_fields: str,
        form_type: Optional[str]
    ) -> str:
        """Construct optimized suggestion prompt with reduced tokens"""
        prompt_parts = [
            f"Gợi ý cho trường '{field_name}'",
            f"Loại form: {form_type}" if form_type else "",
            f"Trường tương tự: {', '.join(similar_fields[:2])}" if similar_fields else "",
        ]
        
        # Add context if available, but limit length
        if context:
            prompt_parts.append(f"Ngữ cảnh: {context[:100]}...")
        
        # Add historical values if available, limit to 3 most recent
        if historical_values:
            prompt_parts.append(f"Giá trị gần đây: {', '.join(historical_values[:3])}")
        
        if related_fields:
            prompt_parts.append(f"Trường liên quan: {related_fields[:100]}...")
        
        prompt_parts.extend([
            "\nYêu cầu:",
            "- 2 gợi ý phù hợp (JSON format)",
            "- Giá trị mặc định tốt nhất",
            "- Lý do ngắn gọn",
            "Ví dụ: {\"suggestions\": [{\"text\": \"...\", \"reason\": \"...\"}], \"default\": \"...\", \"reason\": \"...\"}"
        ])
        
        return "\n".join([p for p in prompt_parts if p])
    def _generate_with_openai(
        self,
        field_name: str,
        historical_values: List[str],
        context: Optional[str],
        form_type: Optional[str],
        related_fields_data: Optional[Dict]
    ) -> Dict[str, Any]:
        """Generate suggestions optimized for OpenAI"""
        similar_fields = self.find_similar_fields(field_name)
        related_fields = self._get_related_fields(field_name, similar_fields, related_fields_data)
        
        prompt = self._build_optimized_prompt(
            field_name,
            similar_fields,
            historical_values,
            context,
            related_fields,
            form_type
        )
        
        response = self._call_ai_api(
            prompt=prompt,
            system_message="You are a form filling assistant. Provide concise suggestions.",
            is_json=True,
            max_tokens=200
        )
        
        return self._parse_suggestion_response(response)
    def _get_enhanced_context(
        self,
        context: Optional[str],
        db_data: List[Dict],
        user_id: str,
        form_type: Optional[str] = None
    ) -> str:
        """
        Tăng cường ngữ cảnh dựa trên lịch sử người dùng, loại form và các thông tin liên quan
        """
        # Khởi tạo context nếu chưa có
        enhanced_context = context or ""

        # Lấy các form gần đây của người dùng cùng loại (nếu có)
        recent_entries = [
            entry for entry in db_data
            if str(entry.get("user_id")) == str(user_id)
            and (not form_type or entry.get("form_data", {}).get("form_type") == form_type)
        ]
        
        # Chọn tối đa 3 mẫu gần nhất để rút trích ngữ cảnh
        recent_entries = sorted(
            recent_entries,
            key=lambda x: x.get("timestamp", ""),
            reverse=True
        )[:3]
        
        # Trích xuất một số trường phổ biến để bổ sung vào context
        for entry in recent_entries:
            form_data = entry.get("form_data", {})
            context_snippet = "; ".join(
                f"{k}: {v}" for k, v in form_data.items() if v and k != "form_type"
            )
            if context_snippet:
                if not isinstance(enhanced_context, str):
                    enhanced_context = str(enhanced_context)

                enhanced_context += f"\nNgữ cảnh từ mẫu trước: {context_snippet}"
        
        return enhanced_context.strip()

    def generate_personalized_suggestions(
        self,
        db_data: List[Dict],
        user_id: str,
        field_code: Optional[str] = None,
        field_name: Optional[str] = None,
        context: Optional[str] = None,
        form_type: Optional[str] = None
        ) -> Dict[str, Any]:
        """Generate personalized suggestions with context"""
        filtered_entries = [
            entry for entry in db_data
            if str(entry.get("user_id")) == str(user_id) and
            (form_type is None or entry.get("form_data", {}).get("form_type") == form_type)
        ]
        sorted_entries = sorted(filtered_entries, key=lambda x: x.get("timestamp", ""), reverse=True)

        # Nếu chưa có context thì trích xuất từ lịch sử biểu mẫu gần đây
        if not context and sorted_entries:
            recent_forms_text = "\n".join([
                json.dumps(entry.get("form_data", {}), ensure_ascii=False)
                for entry in sorted_entries[:3]
            ])
        context = self._get_enhanced_context(context, db_data, user_id, form_type)

        recent_values = []
        matched_fields = set()
        related_fields_data = {}
        best_similarity = 0
        best_field_name = field_name or None

        if field_code:
            similar_fields_cache = {}

            # Nếu chưa có field_name, tìm field_name tốt nhất từ lịch sử
            if not field_name:
                for entry in sorted_entries:
                    form_data = entry.get("form_data", {})

                    # Ưu tiên exact match
                    if field_code in form_data:
                        best_field_name = field_code
                        best_similarity = 1.0
                        break

                    # Tìm trường gần giống
                    for key in form_data.keys():
                        if key not in similar_fields_cache:
                            similar_fields_cache[key] = self._calculate_field_similarity(field_code, key)

                        similarity = similar_fields_cache[key]
                        if similarity > best_similarity:
                            best_similarity = similarity
                            best_field_name = key

                    if best_similarity >= 0.7:
                        break

                # Nếu không tìm được tên tốt hơn, dùng field_code làm tên
                field_name = best_field_name if best_similarity >= 0.5 else field_code
            else:
                # Nếu field_name đã được cung cấp → vẫn kiểm tra độ tương đồng để log lại
                best_field_name = field_name
                best_similarity = self._calculate_field_similarity(field_code, field_name)

            # Xác định các trường liên quan
            similar_fields = self.find_similar_fields(field_name)
            related_fields = self._get_related_field_names(field_name, similar_fields)

            # Thu thập dữ liệu
            for entry in sorted_entries:
                form_data = entry.get("form_data", {})

                # Dữ liệu từ trường chính
                if field_name in form_data:
                    value = form_data[field_name]
                    if value and str(value).strip():
                        recent_values.append(str(value).strip())
                        matched_fields.add(field_name)

                # Dữ liệu từ các trường liên quan
                self._collect_related_data(form_data, related_fields, related_fields_data)

                if len(recent_values) >= 10:
                    break

        frequency_data = Counter(recent_values)
    
        # Sinh đề xuất từ AI
        ai_suggestion = self.generate_suggestions(
            field_name=field_name or field_code or "unknown",
            historical_values=recent_values,
            context=context,
            form_type=form_type,
            related_fields_data=related_fields_data
        )

        # Tính toán giá trị mặc định
        default_value = self._get_default_value(sorted_entries, matched_fields, ai_suggestion)
      
        return {
            "ai_suggestion": ai_suggestion,
            "recent_values": recent_values,
            "default_value": default_value,
            "matched_fields": list(matched_fields),
            "related_fields_data": related_fields_data,
            "reason": ai_suggestion.get("reason", ""),
            "field_matching_info": {
                "requested_field_code": field_code,
                "matched_field_name": field_name,
                "similarity_score": round(best_similarity, 3)
            }
        }
    def _calculate_field_similarity(self, field1: str, field2: str) -> float:
        """Calculate similarity between two field names (0-1)"""
        # Simple implementation - can be enhanced with more sophisticated algorithms
        field1 = field1.lower().strip()
        field2 = field2.lower().strip()
        
        if field1 == field2:
            return 1.0
        
        # Check for partial matches
        if field1 in field2 or field2 in field1:
            return 0.8
            
        # Check for common prefixes/suffixes
        if field1.split('_')[0] == field2.split('_')[0]:
            return 0.6
            
        if field1.split('_')[-1] == field2.split('_')[-1]:
            return 0.5
            
        # Very basic token set similarity
        set1 = set(field1.split('_'))
        set2 = set(field2.split('_'))
        intersection = set1 & set2
        union = set1 | set2
        
        if union:
            return len(intersection) / len(union)
            
        return 0.0

    def _get_related_field_names(self, field_name: str, similar_fields: List[str]) -> List[str]:
        """Get names of related fields"""
        related_fields = self.field_relationships.get(field_name, [])
        if not related_fields and similar_fields:
            for similar_field in similar_fields:
                if similar_field in self.field_relationships:
                    related_fields = self.field_relationships[similar_field]
                    break
        return related_fields[:3] if related_fields else []

    def _collect_related_data(self, form_data: Dict, related_fields: List[str], related_data: Dict):
        """Collect data from related fields"""
        for related_field in related_fields:
            if related_field in form_data and form_data[related_field]:
                related_data[related_field] = form_data[related_field]

    def _collect_field_values(self, form_data: Dict, field_name: str, similar_fields: List[str], 
                            values: List[str], matched_fields: set):
        """Collect field values from form data"""
        for similar_field in similar_fields:
            if similar_field in form_data and form_data[similar_field]:
                val = str(form_data[similar_field]).strip()
                if val and val not in values:
                    values.append(val)
                    matched_fields.add(similar_field)
        
        if field_name in form_data and form_data[field_name]:
            val = str(form_data[field_name]).strip()
            if val and val not in values:
                values.append(val)
                matched_fields.add(field_name)

    def _get_default_value(self, entries: List[Dict], matched_fields: set, ai_suggestion: Dict) -> str:
        """Get default value from most recent entry or AI suggestion"""
        if entries and matched_fields:
            latest_form = entries[0].get("form_data", {})
            for field in matched_fields:
                if field in latest_form:
                    return str(latest_form[field]).strip()
        return ai_suggestion.get("default", "")

    def update_field_value(self, field_name: str, field_value: str, user_id: Optional[str] = None):
        """Update field value with cache invalidation"""
        if not field_name or not isinstance(field_name, str):
            return
            
        try:
            # Update in field matcher
            self.field_matcher.update_field_value(field_name, field_value, user_id)
            
            # Invalidate relevant caches
            self._invalidate_caches_for_field(field_name)
            
            # Update field relationships if needed
            self._update_field_relationships(field_name)
            
            logger.info(f"Updated field {field_name} for user {user_id}")
            
        except Exception as e:
            logger.error(f"Field update failed: {str(e)}")

    def _invalidate_caches_for_field(self, field_name: str):
        """Invalidate all caches related to a field"""
        # Invalidate suggestion cache
        for key in list(self.suggestion_cache.keys()):
            if field_name in str(key):
                del self.suggestion_cache[key]
                
        # Invalidate similar fields cache
        for key in list(self.similar_fields_cache.keys()):
            if field_name in str(key):
                del self.similar_fields_cache[key]
                
        # Invalidate context cache if it contains this field
        for key in list(self.context_cache.keys()):
            if field_name in str(key):
                del self.context_cache[key]

    def _update_field_relationships(self, field_name: str):
        """Update field relationships after modification"""
        try:
            # Rebuild name mapping for this field
            normalized_name = self._normalize_field_name(field_name)
            if normalized_name:
                if normalized_name not in self.field_name_mapping:
                    self.field_name_mapping[normalized_name] = []
                    
                if field_name not in self.field_name_mapping[normalized_name]:
                    self.field_name_mapping[normalized_name].append(field_name)
            
            # Trigger partial relationship rebuild
            self._analyze_field_relationships()
            
        except Exception as e:
            logger.error(f"Failed to update field relationships: {str(e)}")
