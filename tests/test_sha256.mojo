from std.testing import assert_true
from modex.sha256 import SHA256

def main() raises:
    var empty = SHA256()
    empty.update("".as_bytes())
    empty.update("".as_bytes())
    assert_true(empty.hex_digest() == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
    var abc = SHA256()
    abc.update("abc".as_bytes())
    assert_true(abc.hex_digest() == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
    var first_digest = abc.hex_digest()
    assert_true(abc.hex_digest() == first_digest)
    abc.update("\x00".as_bytes())
    assert_true(abc.hex_digest() == "dc1114cd074914bd872cc1f9a23ec910ea2203bc79779ab2e17da25782a624fc")
    assert_true(abc.hex_digest() == abc.hex_digest())
    abc.update("".as_bytes())
    assert_true(abc.hex_digest() == "dc1114cd074914bd872cc1f9a23ec910ea2203bc79779ab2e17da25782a624fc")
    var multi = SHA256()
    multi.update("abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq".as_bytes())
    assert_true(multi.hex_digest() == "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1")
    var split = SHA256()
    var input = "abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq".as_bytes()
    split.update(input[0:0])
    split.update(input[0:13])
    split.update(input[13:])
    assert_true(split.hex_digest() == multi.hex_digest())
    var boundary_lengths = [55, 56, 63, 64, 65]
    var boundary_digests = [
        "9f4390f8d30c2dd92ec9f095b65e2b9ae9b0a925a5258e241c9f1e910f734318",
        "b35439a4ac6f0948b6d6f9e3c6af0f5f590ce20f1bde7090ef7970686ec6738a",
        "7d3e74a05d7db15bce4ad9ec0658ea98e3f06eeecf16b4c6fff2da457ddc2f34",
        "ffe054fe7ae0cb6dc65c3af9b61d5209f439851db43d0ba5997337df154668eb",
        "635361c48bb9eab14198e76ea8ab7f1a41685d6ad62aa9146d301d4f17eb0ae0",
    ]
    for index in range(5):
        var bytes = String("a") * boundary_lengths[index]
        var hash = SHA256()
        hash.update(bytes.as_bytes())
        assert_true(hash.hex_digest() == boundary_digests[index])
    var zero_boundary = SHA256()
    zero_boundary.update((String("a") * 119).as_bytes())
    assert_true(zero_boundary.hex_digest() == "31eba51c313a5c08226adf18d4a359cfdfd8d2e816b13f4af952f7ea6584dcfb")
    var too_long = SHA256()
    too_long.length = 0x1fffffffffffffff
    var rejected_length = False
    try:
        too_long.update("x".as_bytes())
    except:
        rejected_length = True
    assert_true(rejected_length)
    var million = String("a") * 1_000_000
    var million_hash = SHA256()
    var offset = 0
    while offset < million.byte_length():
        var end = min(offset + 997, million.byte_length())
        million_hash.update(million.as_bytes()[offset:end])
        offset = end
    assert_true(million_hash.hex_digest() == "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0")
    print("native SHA-256 vectors: PASS")
