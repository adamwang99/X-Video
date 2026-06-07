"""Unified LLM provider adapter for X-Video.
Providers: local_ollama, gemini, openai, openai_compatible, deepseek, 9router.
Uses xvideo_apikeys for multi-key rotation where applicable.
"""
import json, os, urllib.request, urllib.error

_keymgr = None

def set_keymanager(km):
    global _keymgr
    _keymgr = km

def _post_json(url, payload, headers=None, timeout=240):
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json", **(headers or {})}, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

def _keys(provider):
    if _keymgr:
        return _keymgr.get_all_active_keys(provider) or []
    env = {
        'gemini':'GEMINI_API_KEY', 'openai':'OPENAI_API_KEY', 'openai_compatible':'OPENAI_COMPATIBLE_API_KEY',
        'deepseek':'DEEPSEEK_API_KEY', '9router':'NINEROUTER_API_KEY'
    }.get(provider)
    return [os.environ.get(env)] if env and os.environ.get(env) else []

def _mark_ok(provider, key):
    if _keymgr and key: _keymgr.mark_ok(provider, key)

def _mark_failed(provider, key, err):
    if _keymgr and key: _keymgr.mark_failed(provider, key, str(err))

def complete(prompt, provider='local_ollama', model=None, json_mode=False, temperature=0.4, max_tokens=2400, timeout=240, base_url=None):
    provider = provider or 'local_ollama'
    if provider in ('local','ollama','local_ollama'):
        url = os.environ.get('XVIDEO_OLLAMA','http://localhost:11434') + '/api/generate'
        mdl = model or os.environ.get('XVIDEO_OLLAMA_MODEL','hf.co/unsloth/gemma-4-12b-it-GGUF:Q4_K_M')
        payload = {"model": mdl, "prompt": prompt, "stream": False, "options": {"temperature": temperature, "num_predict": max_tokens}}
        if json_mode: payload['format'] = 'json'
        return _post_json(url, payload, timeout=timeout).get('response','')

    if provider == 'gemini':
        mdl = model or 'gemini-2.0-flash'
        for key in _keys('gemini'):
            try:
                url = f'https://generativelanguage.googleapis.com/v1beta/models/{mdl}:generateContent?key={key}'
                payload = {"contents":[{"parts":[{"text":prompt}]}], "generationConfig":{"temperature":temperature, "maxOutputTokens":max_tokens}}
                if json_mode: payload['generationConfig']['responseMimeType']='application/json'
                d = _post_json(url, payload, timeout=timeout)
                _mark_ok('gemini', key)
                return d.get('candidates',[{}])[0].get('content',{}).get('parts',[{}])[0].get('text','')
            except Exception as e:
                _mark_failed('gemini', key, e)
        raise RuntimeError('No working Gemini key')

    cfg = {
        'openai': ('openai', base_url or os.environ.get('OPENAI_BASE_URL','https://api.openai.com/v1'), model or 'gpt-4o-mini'),
        'openai_compatible': ('openai_compatible', base_url or os.environ.get('OPENAI_COMPATIBLE_BASE_URL','http://127.0.0.1:8000/v1'), model or os.environ.get('OPENAI_COMPATIBLE_MODEL','gpt-4o-mini')),
        'deepseek': ('deepseek', base_url or os.environ.get('DEEPSEEK_BASE_URL','https://api.deepseek.com/v1'), model or 'deepseek-chat'),
        '9router': ('9router', base_url or os.environ.get('NINEROUTER_BASE_URL', os.environ.get('ROUTER9_BASE_URL','https://api.9router.com/v1')), model or os.environ.get('NINEROUTER_MODEL','Tiep')),
    }
    if provider not in cfg:
        raise RuntimeError('Unsupported LLM provider: '+provider)
    key_provider, base, mdl = cfg[provider]
    for key in _keys(key_provider):
        try:
            payload = {"model": mdl, "messages":[{"role":"user","content":prompt}], "temperature": temperature, "max_tokens": max_tokens, "stream": False}
            if json_mode: payload['response_format'] = {"type":"json_object"}
            d = _post_json(base.rstrip('/')+'/chat/completions', payload, headers={"Authorization":"Bearer "+key}, timeout=timeout)
            _mark_ok(key_provider, key)
            return d.get('choices',[{}])[0].get('message',{}).get('content','')
        except Exception as e:
            _mark_failed(key_provider, key, e)
    raise RuntimeError('No working key for '+provider)
