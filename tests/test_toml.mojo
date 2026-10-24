from std.testing import assert_equal, assert_true

from modex.toml import TOML_ARRAY, TOML_BOOLEAN, TOML_DATETIME, TOML_FLOAT, TOML_INTEGER, TOML_LOCAL_DATE, TOML_LOCAL_TIME, TOML_LOCAL_DATETIME, TOML_STRING, TOML_TABLE, TOMLDocument


def main() raises:
    var doc = TOMLDocument("title = \"hello\"\ncount = 12\nactive = true\nratio = 1.5\nwhen = 1979-05-27T07:32:00Z\nitems = [1, \"x\"]\n[owner]\nname = 'Tom'\n")
    assert_equal(doc.nodes[doc.get(doc.root, "title")].kind, TOML_STRING)
    assert_equal(doc.nodes[doc.get(doc.root, "count")].kind, TOML_INTEGER)
    assert_equal(doc.nodes[doc.get(doc.root, "active")].kind, TOML_BOOLEAN)
    assert_equal(doc.nodes[doc.get(doc.root, "ratio")].kind, TOML_FLOAT)
    assert_equal(doc.nodes[doc.get(doc.root, "when")].kind, TOML_DATETIME)
    assert_equal(doc.nodes[doc.get(doc.root, "items")].kind, TOML_ARRAY)
    var owner = doc.get(doc.root, "owner")
    assert_equal(doc.string(doc.get(owner, "name")), "Tom")
    var nested = TOMLDocument("a.b = 2\n[products]\n[[products.item]]\nname='x'\n[[products.item]]\nname='y'\n")
    var a = nested.get(nested.root, "a")
    assert_equal(nested.nodes[nested.get(a, "b")].text, "2")
    var products = nested.get(nested.root, "products")
    var item = nested.get(products, "item")
    assert_equal(nested.nodes[item].kind, TOML_ARRAY)
    assert_equal(len(nested.nodes[item].children), 2)
    var escaped = TOMLDocument("x = \"a\\n\\t\\\"b\"\ny = \"\"\"\nhello\nworld\n\"\"\"\n")
    assert_equal(escaped.string(escaped.get(escaped.root, "x")), "a\n\t\"b")
    assert_equal(escaped.string(escaped.get(escaped.root, "y")), "hello\nworld\n")
    var empty_strings = TOMLDocument("basic = \"\"\nliteral = ''\n")
    assert_equal(empty_strings.string(empty_strings.get(empty_strings.root, "basic")), "")
    assert_equal(empty_strings.string(empty_strings.get(empty_strings.root, "literal")), "")
    var multiline = TOMLDocument("basic = \"\"\"text \"\"\"\nquoted = \"\"\"one \"\"\"\"\nliteral = '''\nraw\\ntext\n'''\ncodepoints = \"\\x41\\e\\u03B1\\U0001F525\"\n")
    assert_equal(multiline.string(multiline.get(multiline.root, "basic")), "text ")
    assert_equal(multiline.string(multiline.get(multiline.root, "quoted")), "one \"")
    assert_equal(multiline.string(multiline.get(multiline.root, "literal")), "raw\\ntext\n")
    assert_equal(multiline.string(multiline.get(multiline.root, "codepoints")), "A\x1Bα🔥")
    var newlines = TOMLDocument("value = \"\"\"one\r\ntwo\r\n\"\"\"\r\nnext=1\r\n")
    assert_equal(newlines.string(newlines.get(newlines.root, "value")), "one\ntwo\n")
    var u64 = TOMLDocument("max = 18446744073709551615\nhex = 0xffffffffffffffff\nmin = -9223372036854775808\n")
    assert_equal(u64.nodes[u64.get(u64.root, "max")].text, "18446744073709551615")
    assert_equal(u64.nodes[u64.get(u64.root, "hex")].kind, TOML_INTEGER)
    var datetime_types = TOMLDocument("date=1979-05-27\ntime=07:32\nlocal=1979-05-27T07:32\noffset=1979-05-27T07:32Z\n")
    assert_equal(datetime_types.nodes[datetime_types.get(datetime_types.root, "date")].kind, TOML_LOCAL_DATE)
    assert_equal(datetime_types.nodes[datetime_types.get(datetime_types.root, "time")].kind, TOML_LOCAL_TIME)
    assert_equal(datetime_types.nodes[datetime_types.get(datetime_types.root, "local")].kind, TOML_LOCAL_DATETIME)
    assert_equal(datetime_types.nodes[datetime_types.get(datetime_types.root, "offset")].kind, TOML_DATETIME)
    var year_zero = TOMLDocument("date=0000-02-29\n")
    assert_equal(year_zero.nodes[year_zero.get(year_zero.root, "date")].kind, TOML_LOCAL_DATE)
    var v11 = TOMLDocument("short = 1979-05-27 07:32Z\nlocal = 07:32\ninline = {a=1,\n b=2,}\n")
    assert_equal(v11.nodes[v11.get(v11.root, "short")].kind, TOML_DATETIME)
    var nested_arrays = TOMLDocument("[[group]]\nname='one'\n[[group.items]]\nvalue=1\n[[group]]\nname='two'\n[[group.items]]\nvalue=2\n")
    var groups = nested_arrays.get(nested_arrays.root, "group")
    assert_equal(len(nested_arrays.nodes[groups].children), 2)
    var implicit = TOMLDocument("[deep.nested.table]\nvalue=1\n[root]\nvalue=2\n")
    assert_equal(implicit.nodes[implicit.get(implicit.root, "root")].kind, TOML_TABLE)
    var invalid: List[String] = [
        "x=1\nx=2", "[a]\nx=1\n[a]\ny=2", "x = 01", "x = \"unterminated",
        "x = 18446744073709551616", "x = -9223372036854775809", "x = 0x10000000000000000",
        "x = +0x2", "x = -0x2", "x = 0xG", "x = 1__0", "x = 01.2", "x = 1.", "x = .1", "x = 1e", "x = 1e+",
        "x = 1e999", "x = 2023-02-29", "x = 2024-13-01", "x = 25:00", "x = 07:32Z",
        "x = 1979-05-27T07:32+24:00", "x = 2024-01-01T23:58:60Z",
        "x = 07:32.5", "x=1979-05-27T07:32+05", "x=1979-05-27T07:32+05:",
        "x = \"\"\"\rtext\"\"\"",
        "x = 2000-01-01T00", "x = 2000-01-01T0", "x = 2000-01-01T00:",
        "x = 2000-01-01T00:0", "x = 2000-01-01T00:00:", "x = 2000-01-01T00:00:0",
        "x = 2000-01-01T00:00:00+", "x = 2000-01-01T00:00:00+0",
        "x = 2000-01-01T00:00:00+00:",
        "x = \"\"\"a\\\n\rb\"\"\"",
        "x = \"\"\"a\\   \r\rb\"\"\"",
        "a = {x=1}\na.y=2", "a.b=1\n[a]", "a=[1]\n[[a]]",
        "a=[{x=1}]\na.x=2", "a=[{x=1}]\n[a.child]", "x=1\rvalue=2"
    ]
    for source in invalid:
        var failed = False
        try:
            var parsed = TOMLDocument(source)
        except:
            failed = True
        assert_true(failed, source)
    print("TOML unit checks: PASS")
