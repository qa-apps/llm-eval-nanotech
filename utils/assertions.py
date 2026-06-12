from playwright.sync_api import Page, Locator, expect

def expect_images_loaded(page: Page) -> None:
    images = page.locator('img')
    count = images.count()

    for i in range(count):
        img = images.nth(i)
        img.scroll_into_view_if_needed()

        result = img.evaluate('''
            (node) => {
                const image = node;
                return {
                    complete: image.complete,
                    naturalWidth: image.naturalWidth
                };
            }
        ''')

        assert result.get('complete') is True
        assert result.get('naturalWidth', 0) > 0

def expect_section_heading_visible(page: Page, heading: str) -> None:
    section_heading = page.get_by_role('heading', name=heading).first
    expect(section_heading).to_be_visible()

def expect_clickable(locator: Locator) -> None:
    expect(locator).to_be_visible()
    expect(locator).to_be_enabled()
