# Configuration Setup

## LLM Configuration

1. Copy `llm_config.json.template` to `llm_config.json`:
   ```bash
   cp ui/llm_config.json.template ui/llm_config.json
   ```

2. Edit `ui/llm_config.json` and replace `YOUR_API_KEY_HERE` with your actual OpenAI API key

3. The `llm_config.json` file is gitignored and will not be committed to the repository

## Security Note

Never commit API keys or secrets to the repository. Always use the template file for reference.
