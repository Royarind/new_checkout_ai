# ===========================================
# LLM PROVIDER CONFIGURATION
# ===========================================

# Choose LLM provider: groq, openai, gemini, openrouter, ollama, azure, or custom
LLM_PROVIDER=openrouter

# ------ OpenRouter Configuration ------
# Get your API key from: https://openrouter.ai/keys
OPENROUTER_API_KEY=your_openrouter_api_key_here
# Recommended models:
# - deepseek/deepseek-chat (Excellent reasoning, very affordable)
# - anthropic/claude-3.5-sonnet (Best for complex tasks)
# - google/gemini-2.0-flash-exp:free (Free tier)  
# - meta-llama/llama-3.3-70b-instruct (Open source, powerful)
OPENROUTER_MODEL=deepseek/deepseek-chat

# ------ Alternative Providers ------

# Groq Configuration
# GROQ_API_KEY=your_groq_api_key_here
# GROQ_MODEL=llama-3.3-70b-versatile

# OpenAI Configuration
# OPENAI_API_KEY=your_openai_api_key_here
# OPENAI_MODEL=gpt-4o-mini

# Google Gemini Configuration
# GEMINI_API_KEY=your_gemini_api_key_here
# GEMINI_MODEL=gemini-2.5-flash

# Ollama (Local) Configuration
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_MODEL=qwen2.5:7b

# ===========================================
# DATABASE CONFIGURATION
# ===========================================
DATABASE_PATH=./checkout_ai.db

# ===========================================
# SECURITY (FOR PRODUCTION)
# ===========================================
SECRET_KEY=your-secret-key-change-this-in-production
JWT_SECRET=your-jwt-secret-change-this-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=30

# ===========================================
# FRONTEND URL
# ===========================================
FRONTEND_URL=http://localhost:5173

# ===========================================
# SMTP EMAIL (For password reset - optional)
# ===========================================
# SMTP_HOST=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USER=your-email@gmail.com
# SMTP_PASSWORD=your-app-password
