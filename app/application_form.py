"""Locate application forms across embedded ATS dialogs without submitting them."""
from __future__ import annotations

import time
import uuid
from pathlib import Path
from .worker_runtime import check_cancelled


def find_form_scope(page):
    candidates = []
    for frame in page.frames:
        try:
            if frame != page.main_frame and not frame.frame_element().is_visible():
                continue
            files = frame.locator('input[type="file"]').count()
            contacts = frame.locator('input[type="email"],input[type="tel"],input[name*="firstname" i],input[name*="lastname" i]')
            visible = sum(contacts.nth(i).is_visible() for i in range(min(contacts.count(), 12)))
            if files or visible >= 2:
                candidates.append((files * 10 + visible, frame))
        except Exception:
            continue
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def wait_for_form_scope(page, timeout_seconds=25, *, exclude_url=None):
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        check_cancelled()
        scope = find_form_scope(page)
        if scope is not None and (not exclude_url or scope.url != exclude_url):
            return scope
        if not exclude_url and consent_pending(page):
            return None
        page.wait_for_timeout(500)
    return None


def consent_pending(page):
    for frame in page.frames:
        try:
            checkbox = frame.locator('#acceptRgpd')
            if checkbox.count() and checkbox.is_visible() and not checkbox.is_checked():
                return True
        except Exception:
            continue
    return False


def accept_confirmed_privacy(page):
    """Only called with explicit approval for this invocation and this job."""
    for frame in page.frames:
        checkbox = frame.locator('#acceptRgpd')
        if checkbox.count() and checkbox.is_visible():
            if not checkbox.is_checked():
                # The Cegid checkbox is styled outside the viewport; its visible
                # associated label is the intended click target.
                label = frame.locator('label[for="acceptRgpd"]')
                if label.count() and label.is_visible():
                    label.click(timeout=3000)
                else:
                    checkbox.check(timeout=3000)
            if not checkbox.is_checked():
                raise ValueError('L’accord à la charte n’a pas été enregistré.')
            return True
    return False


def requires_combined_packet(scope):
    """Cegid OneClick exposes just one CV import before final submission."""
    return ('/consent' in scope.url and scope.locator('#cv-import').count() == 1
            and scope.locator('input[type="file"]').count() == 1)


def build_application_packet(cv: Path, letter: Path, target: Path):
    from pypdf import PdfReader, PdfWriter
    if cv.suffix.lower() != '.pdf':
        raise ValueError('Ce formulaire accepte un dossier unique : sélectionnez un CV PDF pour y joindre la lettre.')
    target.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    writer.append(str(cv))
    cv_pages = len(writer.pages)
    writer.append(str(letter))
    temporary = target.with_name(f'{target.stem}.{uuid.uuid4().hex}.tmp.pdf')
    try:
        with temporary.open('wb') as stream:
            writer.write(stream)
        with temporary.open('rb') as stream:
            if len(PdfReader(stream).pages) <= cv_pages:
                raise ValueError('La lettre est absente du dossier PDF.')
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
        writer.close()
    return {'path': str(target), 'cv_pages': cv_pages, 'pages': len(PdfReader(target).pages)}
