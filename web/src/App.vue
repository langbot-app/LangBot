<template>
  <v-app>

    <v-layout>
      <v-navigation-drawer id="navigation-drawer" :width="160" app permanent rail>
        <v-list-item id="logo-list-item">
          <template v-slot:prepend>
            <v-img src="@/assets/langbot-logo-block.png" height="32" width="32"></v-img>
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
              <v-list-item id="about-list-item" title="关于" prepend-icon="mdi-cog-outline" v-tooltip="关于">
              </v-list-item>
            </v-list>
          </div>
        </template>
      </v-navigation-drawer>

      <v-main>
        <router-view />
      </v-main>
    </v-layout>
  </v-app>
</template>

<script setup>
</script>

<style scoped>
#navigation-drawer {
  display: flex;
  flex-direction: column;
}

#logo-list-item {
  margin-left: -0.2rem;
  margin-block: 0.5rem;
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
</style>