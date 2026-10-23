"""Short, locally served OAuth setup guide without secret values."""
import html

GUIDES = {
    'zh': ('连接 Gmail：只需配置一次', [
        '用你自己的 Google 账号打开 Google Cloud Console，创建或选择一个项目。',
        '在“API 和服务 → 库”中启用 Gmail API。',
        '打开 Google Auth Platform：填写应用名称、联系邮箱，配置 OAuth 同意屏幕。个人使用时选择 External；在 Audience 的测试用户中加入要连接的 Gmail 地址。',
        '在 Data Access 中添加 gmail.readonly 权限。它只能读取，不能发送或删除邮件。',
        '打开 Clients → Create client，应用类型选 Desktop app（桌面应用）。创建后复制 Client ID 和 Client secret。不要选择 Web application。',
        '返回本项目“个人档案与账号”。先选正确的人，再把 ID 和密钥填入 Google 配置，点击保存。密钥仅在本机加密保存。',
        '用 start.bat 启动系统（端口 8765），点击“连接 Gmail”，再点击出现的授权链接。在 Google 页面选正确的邮箱并授权。',
        '授权完成后关闭该标签，重新打开“个人档案与账号”，核对显示的邮箱。若失败：确认 Gmail API 已启用、已添加测试用户、客户端类型是桌面应用，并重新连接。',
        '测试模式授权可能在七天后失效，需要重新授权。撤销权限可到 Google 账号的第三方连接页；“断开本地连接”仅删除本地令牌。',
        '连接后可选择开启“自动读取登录验证码”。只尝试当前网站发给当前账号的近期验证码；不确定时保留页面让你处理。不会自动找回密码。Gmail 仍是可选功能。']),
    'fr': ('Connecter Gmail : configuration unique', [
        'Ouvrez Google Cloud Console avec votre compte. Créez ou sélectionnez un projet.',
        'Dans API et services → Bibliothèque, activez Gmail API.',
        'Dans Google Auth Platform, configurez le nom et l’email de contact. Pour un usage personnel, choisissez External et ajoutez votre adresse Gmail aux utilisateurs de test dans Audience.',
        'Dans Data Access, ajoutez gmail.readonly : lecture seule, sans envoi ni suppression.',
        'Dans Clients → Create client, choisissez Desktop app. Copiez Client ID et Client secret. Ne choisissez pas Web application.',
        'Dans Profils & comptes, sélectionnez la bonne personne, remplissez et enregistrez la configuration Google. Les secrets restent chiffrés sur ce PC.',
        'Lancez start.bat (port 8765). Cliquez Connecter Gmail puis le lien affiché. Choisissez le bon compte Google et autorisez.',
        'Fermez cet onglet puis rouvrez Profils & comptes et vérifiez l’adresse. En cas d’échec, vérifiez Gmail API, utilisateur de test et client Desktop app.',
        'En mode test, l’autorisation peut expirer après sept jours. Pour la révoquer, utilisez les connexions tierces du compte Google. Déconnecter localement retire uniquement le jeton local.',
        'Après connexion, la lecture des codes de connexion est facultative : codes récents du même site et du même compte uniquement. Les autres vérifications restent manuelles. Aucune récupération automatique de mot de passe.']),
    'en': ('Connect Gmail: one-time setup', [
        'Open Google Cloud Console with your own account. Create or select a project.',
        'Enable Gmail API under APIs & Services → Library.',
        'Configure Google Auth Platform branding and contact email. For personal use choose External and add the Gmail address as a test user under Audience.',
        'Add gmail.readonly under Data Access. This permits reading, without sending or deleting messages.',
        'Under Clients → Create client, select Desktop app. Copy Client ID and Client secret. Do not select Web application.',
        'Open Profiles & accounts in this app, select the right person, then save the Google configuration. Secrets are encrypted on this PC.',
        'Run start.bat on port 8765. Click Connect Gmail, then the displayed authorization link. Select the correct Google mailbox and approve access.',
        'Close the authorization tab, reopen Profiles & accounts and check the mailbox address. If unsuccessful, check Gmail API, test user and Desktop app client type.',
        'Testing-mode grants may expire after seven days. Revoke access in Google Account third-party connections. Disconnect locally removes only the local token.',
        'After connecting, optionally enable email login codes: recent codes from the same site for the same account only. Other challenges stay manual. Password recovery is never automated. Gmail remains optional.']),
}


def render(language):
    title, steps = GUIDES.get(language, GUIDES['en'])
    return '<!doctype html><html lang="'+html.escape(language if language in GUIDES else 'en')+'"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>'+title+'</title><link rel="stylesheet" href="/static/connection.css"><main><img class="connection-scene" src="/static/artwork/angelina/read.png" alt="" aria-hidden="true"><h1>'+title+'</h1><ol>'+''.join('<li>'+html.escape(step)+'</li>' for step in steps)+'</ol><p><a href="https://console.cloud.google.com/" target="_blank" rel="noopener noreferrer">Google Cloud Console ↗</a></p><p><a href="https://developers.google.com/identity/protocols/oauth2/native-app">Google OAuth documentation</a></p><p><a href="/">Job Apply Assistant</a></p></main></html>'
