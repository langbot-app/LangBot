<template>
  <v-app>
    <v-snackbar v-model="snackbar" :color="color" :timeout="timeout" :location="location">
      {{ text }}
    </v-snackbar>

    <v-layout>
      <v-navigation-drawer id="navigation-drawer" :width="160" app permanent rail>
        <v-list-item id="logo-list-item">
          <template v-slot:prepend>
            <div id="logo-container">
              <v-img id="logo-img" src="@/assets/langbot-logo-block.png" height="32" width="32"></v-img>

              <div id="version-chip"
                v-tooltip="proxy.$store.state.version + (proxy.$store.state.debug ? ' (调试模式已启用)' : '')"
                :style="{ 'background-color': proxy.$store.state.debug ? '#27aa27' : '#1e9ae2' }">
                {{ proxy.$store.state.version }}
              </div>
            </div>
          </template>
        </v-list-item>
        <v-divider></v-divider>
        <v-list density="compact" nav>
          <v-list-item to="/" title="仪表盘" value="dashboard" prepend-icon="mdi-speedometer" v-tooltip="仪表盘">
          </v-list-item>
          <v-list-item to="/settings" title="设置" value="settings" prepend-icon="mdi-toggle-switch-outline"
            v-tooltip="设置">
          </v-list-item>
          <v-list-item to="/logs" title="日志" value="logs" prepend-icon="mdi-file-outline" v-tooltip="日志">
          </v-list-item>
          <v-list-item to="/plugins" title="插件" value="plugins" prepend-icon="mdi-puzzle-outline" v-tooltip="插件">
          </v-list-item>
        </v-list>
        <template v-slot:append>
          <div>
            <v-list density="compact" nav>
              <v-dialog max-width="500" persistent v-model="taskDialogShow">
                <template v-slot:activator="{ props: activatorProps }">
                  <v-list-item id="system-tasks-list-item" title="任务列表" prepend-icon="mdi-align-horizontal-left"
                    v-tooltip="任务列表" v-bind="activatorProps">
                  </v-list-item>
                </template>

                <template v-slot:default="{ isActive }">
                  <TaskDialog :dialog="{ show: isActive }" @close="closeTaskDialog" />
                </template>
              </v-dialog>

              <v-list-item id="about-list-item" title="系统信息" prepend-icon="mdi-cog-outline" v-tooltip="系统信息">
                <v-menu activator="parent" :close-on-content-click="false" location="end">
                  <v-list>
                    <v-list-item @click="showAboutDialog">
                      <v-list-item-title>
                        关于 LangBot

                        <v-dialog max-width="400" persistent v-model="aboutDialogShow">
                          <template v-slot:default="{ isActive }">
                            <AboutDialog :dialog="{ show: isActive }" @close="closeAboutDialog" />
                          </template>
                        </v-dialog>
                      </v-list-item-title>
                    </v-list-item>

                    <v-list-item @click="openDocs">
                      <v-list-item-title>
                        查看文档
                      </v-list-item-title>
                    </v-list-item>

                    <v-list-item @click="reload('platform')">
                      <v-list-item-title>
                        重载消息平台
                      </v-list-item-title>
                    </v-list-item>

                    <v-list-item @click="reload('plugin')">
                      <v-list-item-title>
                        重载插件
                      </v-list-item-title>
                    </v-list-item>
                  </v-list>
                </v-menu>
              </v-list-item>
            </v-list>
          </div>
        </template>
      </v-navigation-drawer>

      <v-main style="background-color: #f6f6f6;">
        <router-view />
      </v-main>
    </v-layout>
  </v-app>
</template>

<script setup>
import { getCurrentInstance } from 'vue'
import { provide, ref, watch } from 'vue';

import TaskDialog from '@/components/TaskListDialog.vue'
import AboutDialog from '@/components/AboutDialog.vue'

const { proxy } = getCurrentInstance()

const snackbar = ref(false);
const color = ref('success');
const text = ref('');
const location = ref('top');
const timeout = ref(2000);

function success(content) {
  snackbar.value = true;
  color.value = 'success';
  text.value = content;
}

function error(content) {
  snackbar.value = true;
  color.value = 'error';
  text.value = content;
}

function warning(content) {
  snackbar.value = true;
  color.value = 'warning';
  text.value = content;
}

function info(content) {
  snackbar.value = true;
  color.value = 'primary';
  text.value = content;
}

const taskDialogShow = ref(false)

function showTaskDialog() {
  taskDialogShow.value = true
}

function closeTaskDialog() {
  taskDialogShow.value = false
}

provide('snackbar', { success, error, warning, info, location, timeout });

function openDocs() {
  window.open('https://docs.langbot.app', '_blank')
}

const reloadScopeLabel = {
  'platform': "消息平台",
  'plugin': "插件"
}

function reload(scope) {
  let label = reloadScopeLabel[scope]
  proxy.$axios.post('/system/reload',
    { scope: scope },
    { headers: { 'Content-Type': 'application/json' } }
  ).then(response => {
    if (response.data.code === 0) {
      success(label+'已重载')

      // 关闭菜单
    } else {
      error(label+'重载失败：' + response.data.message)
    }
  }).catch(err => {
    error(label+'重载失败：' + err)
  })

}

const aboutDialogShow = ref(false)

function showAboutDialog() {
  aboutDialogShow.value = true
}

function closeAboutDialog() {
  aboutDialogShow.value = false
}
</script>

<style scoped>
#navigation-drawer {
  display: flex;
  flex-direction: column;
}

#logo-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  margin-left: -0.2rem;
}

#logo-img {
  /* margin-left: -0.2rem; */
}

#logo-list-item {
  margin-top: 0.5rem;
  margin-bottom: 1.5rem;
}

#version-chip {
  position: absolute;
  top: 0;
  right: 0;
  margin-top: 2.4rem;
  margin-right: 0.3rem;
  font-size: 0.55rem;
  font-weight: 500;
  padding-inline: 0.4rem;
  text-align: center;
  background-color: #c79a47;
  color: white;
  border-radius: 0.5rem;
  border: 1px solid #fff;
  box-shadow: 0 0 0.1rem 0 rgba(0, 0, 0, 0.5);
  user-select: none;
}

#about-list-item {
  justify-self: flex-end;
}

#about-list-item:hover {
  cursor: pointer;
  background-color: #eee;
}

#about-list-item:active {
  background-color: #ddd;
}

#system-tasks-list-item:hover {
  cursor: pointer;
  background-color: #eee;
}

#system-tasks-list-item:active {
  background-color: #ddd;
}
</style>
