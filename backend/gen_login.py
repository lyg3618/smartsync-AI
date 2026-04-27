# gen_login.py - generates Login.vue with real backend auth
content = """<template>
  <div class=""login-page"">
    <div class=""login-bg"">
      <div class=""orb orb-1""></div><div class=""orb orb-2""></div><div class=""orb orb-3""></div>
    </div>
    <div class=""login-card fade-slide-up"">
      <div class=""brand"">
        <div class=""brand-icon""><el-icon size=""28""><Headset /></el-icon></div>
        <div><h1 class=""brand-name"">SmartSync</h1><p class=""brand-sub"">\u667a\u80fd\u4f1a\u8bae\u6d1e\u5bdf\u4e0e\u4efb\u52a1\u4e2d\u67a2</p></div>
      </div>
      <el-form :model=""form"" size=""large"" @submit.prevent=""handleLogin"">
        <el-form-item><el-input v-model=""form.username"" placeholder=""\u7528\u6237\u540d"" prefix-icon=""User"" /></el-form-item>
        <el-form-item><el-input v-model=""form.password"" type=""password"" placeholder=""\u5bc6\u7801"" prefix-icon=""Lock"" show-password /></el-form-item>
        <div v-if=""error"" class=""error-tip"">{{ error }}</div>
        <el-button type=""primary"" native-type=""submit"" class=""login-btn"" :loading=""loading"" size=""large"" round>\u767b\u5f55\u7cfb\u7edf</el-button>
      </el-form>
      <div class=""login-accounts"">
        <p class=""accounts-label"">\u5feb\u901f\u767b\u5f55</p>
        <div class=""accounts-row"">
          <span v-for=""a in quickAccounts"" :key=""a.username"" class=""account-chip"" @click=""quickLogin(a)"">{{ a.label }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from ""vue""
import { useRouter } from ""vue-router""
import { ElMessage } from ""element-plus""
import axios from ""axios""

const router = useRouter()
const loading = ref(false)
const error = ref(\"\")
const form = ref({ username: \"\", password: \"\" })

const quickAccounts = [
  { label: ""\u7ba1\u7406\u5458"", username: ""admin"", password: ""admin123"" },
  { label: ""\u5f20\u4f1f"",   username: ""zhang"", password: ""zhang123"" },
  { label: ""\u674e\u5a1c"",   username: ""li"",    password: ""li123""    },
  { label: ""\u738b\u82b3"",   username: ""wang"",  password: ""wang123""  },
]

function quickLogin(account) {
  form.value.username = account.username
  form.value.password = account.password
  handleLogin()
}

async function handleLogin() {
  if (!form.value.username || !form.value.password) { error.value = ""\u8bf7\u8f93\u5165\u7528\u6237\u540d\u548c\u5bc6\u7801""; return }
  error.value = \"\"
  loading.value = true
  try {
    const fd = new URLSearchParams()
    fd.append(""username"", form.value.username)
    fd.append(""password"", form.value.password)
    const res = await axios.post(""http://localhost:8000/auth/login"", fd, {
      headers: { ""Content-Type"": ""application/x-www-form-urlencoded"" }
    })
    const { access_token, user } = res.data
    localStorage.setItem(""smartsync_token"", access_token)
    localStorage.setItem(""smartsync_user"", JSON.stringify(user))
    ElMessage.success(`\u767b\u5f55\u6210\u529f\uff0c\u6b22\u8fce ${user.name}\uff01`)
    router.push(""/dashboard"")
  } catch (e) {
    const msg = e.response?.data?.detail || ""\u767b\u5f55\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5\u7528\u6237\u540d\u548c\u5bc6\u7801""
    error.value = msg
    ElMessage.error(msg)
  } finally { loading.value = false }
}
</script>

<style scoped>
.login-page{min-height:100vh;display:flex;align-items:center;justify-content:center;position:relative;overflow:hidden;background:var(--bg);}
.login-bg{position:absolute;inset:0;}
.orb{position:absolute;border-radius:50%;filter:blur(80px);opacity:0.25;animation:float 8s ease-in-out infinite;}
.orb-1{width:500px;height:500px;background:radial-gradient(#4F6EF6,transparent);top:-100px;left:-100px;}
.orb-2{width:400px;height:400px;background:radial-gradient(#7c5cfc,transparent);bottom:-50px;right:-50px;animation-delay:-3s;}
.orb-3{width:300px;height:300px;background:radial-gradient(#22c55e,transparent);top:50%;left:50%;animation-delay:-5s;}
.login-card{position:relative;z-index:1;background:rgba(20,22,38,.8);backdrop-filter:blur(24px);border:1px solid var(--border);border-radius:24px;padding:48px 44px;width:420px;box-shadow:var(--shadow);}
.brand{display:flex;align-items:center;gap:14px;margin-bottom:36px;}
.brand-icon{width:56px;height:56px;border-radius:16px;background:linear-gradient(135deg,var(--primary),var(--accent));display:flex;align-items:center;justify-content:center;color:#fff;}
.brand-name{font-size:22px;font-weight:700;color:var(--text);}
.brand-sub{font-size:12px;color:var(--text-muted);margin-top:2px;}
.error-tip{color:#ef4444;font-size:13px;margin:-6px 0 12px;padding:8px 12px;background:rgba(239,68,68,.1);border-radius:8px;border:1px solid rgba(239,68,68,.2);}
.login-btn{width:100%;margin-top:8px;font-size:15px;font-weight:600;height:48px;background:linear-gradient(135deg,var(--primary),var(--accent)) !important;border:none !important;letter-spacing:1px;}
.login-accounts{margin-top:24px;padding-top:20px;border-top:1px solid var(--border);}
.accounts-label{font-size:11px;color:var(--text-muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:10px;}
.accounts-row{display:flex;gap:8px;flex-wrap:wrap;}
.account-chip{padding:5px 14px;border-radius:20px;background:rgba(79,110,246,.1);border:1px solid rgba(79,110,246,.25);color:var(--primary);font-size:12px;font-weight:500;cursor:pointer;transition:all .2s;}
.account-chip:hover{background:rgba(79,110,246,.2);border-color:rgba(79,110,246,.5);transform:translateY(-1px);}
</style>
"""

path = r""d:\Desktop\AI\u4f1a\u8bae\smartsync\frontend\src\views\Login.vue""
with open(path, ""w"", encoding=""utf-8"") as f: f.write(content)
print(""Login.vue OK"")