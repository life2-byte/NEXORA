"""Remote providers ki list: naam, protocol aur default URL. Custom mein user apna URL deta hai."""

# key -> (label, kind, base_url, default_model_hint)
REMOTE_PRESETS = {
    "anthropic": ("Anthropic (Claude)", "anthropic", "https://api.anthropic.com", "claude-sonnet-4-5"),
    "openai": ("OpenAI", "openai", "https://api.openai.com/v1", "gpt-4o-mini"),
    "gemini": ("Google (Gemini)", "openai", "https://generativelanguage.googleapis.com/v1beta/openai", "gemini-3.5-flash-lite"),
    "groq": ("Groq", "openai", "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
    "openrouter": ("OpenRouter", "openai", "https://openrouter.ai/api/v1", "openai/gpt-4o-mini"),
    "custom": ("Custom (OpenAI-compatible)", "openai", "", ""),
}

LOCAL_KINDS = {
    "ollama": ("Ollama", "ollama", "http://127.0.0.1:11434"),
    "openai": ("OpenAI-compatible (LM Studio, llama.cpp, vLLM...)", "openai", "http://127.0.0.1:1234/v1"),
}