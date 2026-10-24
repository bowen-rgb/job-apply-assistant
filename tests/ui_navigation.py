"""Navigate through the production main menu, for service/feature browser tests."""

def navigate(page, target):
    page.wait_for_load_state('domcontentloaded')
    target={'jobsNav':'jobs','profileNav':'profile','pipelineNav':'pipeline','overviewNav':'overview',
            'guideNav':'guide','qrNav':'qr','accountsNav':'accounts','platformLoginNav':'logins',
            'pendingTasksNav':'pending','pfeNav':'pfe'}.get(target,target)
    if not page.locator('#mainMenuView').count():
        legacy={'jobs':'jobsNav','profile':'profileNav','pipeline':'pipelineNav','overview':'overviewNav','guide':'guideNav','qr':'qrNav','accounts':'accountsNav','logins':'platformLoginNav','pending':'pendingTasksNav','pfe':'pfeNav'}
        page.locator('#'+legacy.get(target,target)).click()
        return
    page.locator('#workspaceMenuButton').click()
    page.locator('#menuSearch').fill(target)
    page.locator(f'#menuPageGrid [data-menu-page="{target}"]').click()


def set_appearance(page, value):
    previous=page.evaluate("document.body.dataset.workspaceView")
    navigate(page,'appearance')
    page.locator('#angelinaMode').select_option(value)
    if previous and previous!='profile':navigate(page,previous)


def toggle_guidance(page):
    options=page.locator('#workspaceOptions')
    if not options.evaluate('(e)=>e.open'):options.locator('summary').click()
    page.locator('#simpleModeToggle').click()
