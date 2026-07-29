"""Test Scrapling API properly"""
from scrapling.parser import Selector

page = Selector('<div><p class="test">Hello World</p><p>Another para</p><span>Extra</span></div>')
els = page.css('.test')
print(f"css() returns: {type(els).__name__}")
if els:
    el = els[0]
    print(f"Element: {type(el).__name__}")
    print(f"  dir: {[x for x in dir(el) if not x.startswith('_')]}")

# Try text_content - might be a TextHandler
tc = el.text_content
print(f"  text_content type: {type(tc).__name__}")
print(f"  text_content value: {tc}")

# Try treating as string
print(f"  str(el): {str(el)[:80]}")

# Try .text (might be an attribute)
if hasattr(el, 'text'):
    print(f"  .text: {el.text}")

# Try .attrib
if hasattr(el, 'attrib'):
    print(f"  .attrib: {el.attrib}")

# Check if css selectors work
all_p = page.css('p')
print(f"\nAll p elements: {len(all_p)}")
for p in all_p:
    tc = p.text_content
    print(f"  p.text_content: {tc}")

# Check ::text pseudo selector
texts = page.css('p::text')
print(f"\np::text: {len(texts)} elements")
for t in texts:
    print(f"  text_content: {t.text_content}")

# Try using get() method
text_val = page.css('p::text').get()
print(f"\nFirst p::text via get(): {text_val}")

all_texts = page.css('p::text').getall()
print(f"All p::text via getall(): {all_texts}")

print("\nDone!")
