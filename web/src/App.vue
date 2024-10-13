<template>
  <v-app>

    <v-layout>
      <v-navigation-drawer :width="160" app permanent expand-on-hover>
        <v-list density="compact" nav>
          <v-list-item to="/" title="仪表盘" value="dashboard" prepend-icon="mdi-view-dashboard-outline">
          </v-list-item>
          <v-list-item to="/settings" title="配置" value="settings" prepend-icon="mdi-cog-outline">
          </v-list-item>
          <v-list-item to="/logs" title="日志" value="logs" prepend-icon="mdi-file-outline">
          </v-list-item>
          <v-list-item to="/plugins" title="插件" value="plugins" prepend-icon="mdi-puzzle-outline">
          </v-list-item>
        </v-list>
      </v-navigation-drawer>

      <v-main>
        <router-view />
      </v-main>
    </v-layout>
  </v-app>
</template>

<script setup>
</script>
