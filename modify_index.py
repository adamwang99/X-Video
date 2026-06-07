import re

with open('frontend/index.html', 'r') as f:
    content = f.read()

pattern = re.compile(r'<script[^>]*>.*?</script>', re.DOTALL)

def replace_func(match):
    tag = match.group(0)
    if 'src=' in tag:
        return tag
    if 'pollTtsReady' not in tag:
        return tag
    inner_match = re.search(r'>(.*?)</script>', tag, re.DOTALL)
    if not inner_match:
        return tag
    inner = inner_match.group(1)
    if '_ttsStartTime' not in inner:
        global_vars = '''let _ttsStartTime = null;
 let _ttsTimeoutReached = false;
 let _ttsPollTimer = null;

 '''
        inner = global_vars + inner
    new_pollTtsReady = '''function pollTtsReady(){
  if (!_ttsStartTime) _ttsStartTime = Date.now();
  var elapsed = Date.now() - _ttsStartTime;
  if (elapsed > 120000) { // 2 minutes
    clearTimeout(_ttsPollTimer);
    var overlay=document.getElementById('ttsOverlay');
    var statusText=overlay.querySelector('.tts-status-text');
    var detailText=overlay.querySelector('.tts-detail-text');
    var spinner=overlay.querySelector('.tts-spinner');
    var dots=overlay.querySelector('.tts-dots');
    spinner.style.display='none';
    dots.style.display='none';
    statusText.textContent='❌ Lỗi';
    detailText.textContent='Quá thời gian chờ model TTS (2 phút). Vui lòng tải lại ứng dụng.';
    return;
  }
  fetch('/api/warmup-tts').then(function(r){return r.json()}).then(function(d){
    var overlay=document.getElementById('ttsOverlay');
    var detail=document.getElementById('overlayDetail');
    if(d.status==='ready'){
      overlay.classList.add('hidden');
      clearTimeout(_ttsPollTimer);
      updateTtsStatus('online','TTS Online');
    } else {
      if(detail) detail.innerHTML=(d.detail||'Đang tải model...').replace(/\n/g,'<br>');
      if(!_ttsTimeoutReached) {
        _ttsPollTimer=setTimeout(pollTtsReady,3000);
        updateTtsStatus('loading','Đang tải...');
      }
    }
  }).catch(function(){
    if(!_ttsTimeoutReached) {
      _ttsPollTimer=setTimeout(pollTtsReady,5000);
    }
  });
}'''
    inner = re.sub(r'function pollTtsReady\([^}]*\}\n)', new_pollTtsReady, inner, flags=re.DOTALL)
    new_inner = '>' + inner + '</script>'
    return re.sub(r'>(.*?)</script>', new_inner, tag, flags=re.DOTALL)

new_content = pattern.sub(replace_func, content)

with open('frontend/index.html', 'w') as f:
    f.write(new_content)

print('Modified index.html with TTS timeout')
