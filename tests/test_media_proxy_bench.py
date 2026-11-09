import hashlib
import importlib.util
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace

from PIL import Image,PngImagePlugin
import pytest

spec=importlib.util.spec_from_file_location('proxy_builder',Path(__file__).resolve().parents[1]/'scripts/media_bench/build_proxies.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)


def png(mode='RGB',color=(45,97,167)):
    image=Image.new(mode,(32,24),color);stream=BytesIO();image.save(stream,format='PNG');return stream.getvalue()


@pytest.mark.parametrize('fmt,kind',[('jpeg','JPEG'),('webp','WEBP')])
def test_derivative_size_format_and_original_hash(fmt,kind):
    source=png();pin=hashlib.sha256(source).hexdigest();encoded,size=builder.encode(source,fmt)
    out=Image.open(BytesIO(encoded));assert out.format==kind and out.size==(32,24) and size==[32,24]
    assert hashlib.sha256(source).hexdigest()==pin
    assert not out.getexif()


def test_pinned_source_wrong_hash_and_symlink(tmp_path):
    p=tmp_path/'source.png';p.write_bytes(png())
    with pytest.raises(ValueError,match='BYTE_PIN_MISMATCH'):builder.read_pin(p,'0'*64)
    link=tmp_path/'link.png';link.symlink_to(p)
    with pytest.raises(ValueError,match='CANONICAL'):builder.read_pin(link,hashlib.sha256(p.read_bytes()).hexdigest())


def test_metadata_png_never_served_as_public_baseline():
    stream=BytesIO();info=PngImagePlugin.PngInfo();info.add_text('test','metadata')
    Image.new('RGB',(8,8)).save(stream,format='PNG',pnginfo=info)
    with pytest.raises(ValueError,match='PNG_METADATA_NOT_PUBLIC'):builder.png_chunks(stream.getvalue())
    safe=builder.public_png(stream.getvalue());assert b'tEXt' not in safe
    assert Image.open(BytesIO(safe)).tobytes()==Image.open(BytesIO(stream.getvalue())).tobytes()
    assert builder.encode(stream.getvalue(),'jpeg')[1]==[8,8]


def test_trailing_bytes_and_transparency_rejected():
    with pytest.raises(ValueError,match='TRAILING'):builder.png_chunks(png()+b'extra')
    with pytest.raises(ValueError,match='OPAQUE'):builder.encode(png('RGBA',(1,2,3,128)),'jpeg')


def test_unknown_encoder_not_silently_selected():
    with pytest.raises(ValueError,match='EXPLICIT_PROXY_FORMAT'):builder.encode(png(),'other')


def test_relative_paths_cannot_escape(tmp_path):
    for value in ['../secret.png','/absolute.png','a/../b.png','a\\b.png']:
        with pytest.raises(ValueError):builder.safe_join(tmp_path,value)


def test_existing_output_and_low_disk_leave_sources_untouched(tmp_path,monkeypatch):
    plan=tmp_path/'plan.json';plan.write_text(json.dumps(dict(purpose='LOCAL_PLAYBACK_ONLY_NOT_INFERENCE',original_png_written=False,rows=[])))
    pin=hashlib.sha256(plan.read_bytes()).hexdigest();out=tmp_path/'new'
    monkeypatch.setattr(builder.shutil,'disk_usage',lambda _:SimpleNamespace(free=8*1024**3-1))
    with pytest.raises(ValueError,match='LOW_DISK'):builder.build(plan,pin,out)
    assert not out.exists()
    out.mkdir()
    with pytest.raises(ValueError,match='NEW_CANONICAL_OUTPUT'):builder.build(plan,pin,out)
