<template>
  <div class="pane-website">
    <pane-header
      class="pane-website__header"
      :paneId="paneId"
      :show-search="false"
      :show-name="true"
    >
      <hr />
      <Btn
        v-if="locked"
        type="button"
        class="-text"
        @click="unlockUrl"
        title="Unlock URL editing"
      >
        <i class="icon-locked"></i>
      </Btn>
      <Btn
        v-if="url && !locked"
        type="button"
        class="-text"
        @click="editing = !editing"
        title="Edit URL"
      >
        <i class="icon-edit"></i>
      </Btn>
      <Btn
        type="button"
        class="-text"
        @click="toggleInteractive"
        :title="interactive ? 'Disable interaction' : 'Enable interaction'"
      >
        <i :class="interactive ? 'icon-click' : 'icon-hidden'"></i>
      </Btn>
      <Btn type="button" class="-text" @click="reload" title="Reload">
        <i class="icon-refresh"></i>
      </Btn>
    </pane-header>
    <div v-if="!url || (!locked && editing)" class="pane-website__input pane-overlay">
      <form @submit.prevent="submitUrl">
        <input
          ref="urlInput"
          type="text"
          placeholder="Enter website URL..."
          class="form-control"
          v-model="urlInput"
          :disabled="locked"
        />
      </form>
    </div>
    <iframe
      v-if="url"
      ref="iframe"
      :key="iframeKey"
      :src="url"
      class="pane-website__iframe"
      :class="{
        '-interactive': interactive,
        '-invert': invert
      }"
      sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
      frameborder="0"
      allowfullscreen
    ></iframe>
    <div v-else class="pane-website__empty">
      <p>Enter a URL above to embed a website</p>
    </div>
  </div>
</template>

<script lang="ts">
import { Component, Mixins, Watch } from 'vue-property-decorator'

import PaneMixin from '@/mixins/paneMixin'
import PaneHeader from '../panes/PaneHeader.vue'
import Btn from '@/components/framework/Btn.vue'

@Component({
  components: { PaneHeader, Btn },
  name: 'Website'
})
export default class Website extends Mixins(PaneMixin) {
  urlInput = ''
  editing = false
  iframeKey = 0

  private _reloadInterval: number | null = null

  get url() {
    return this.$store.state[this.paneId]?.url
  }

  get interactive() {
    return this.$store.state[this.paneId]?.interactive
  }

  get invert() {
    return this.$store.state[this.paneId]?.invert
  }

  get locked() {
    return this.$store.state[this.paneId]?.locked
  }

  get reloadTimer() {
    return this.$store.state[this.paneId]?.reloadTimer
  }

  mounted() {
    if (this.url) {
      this.urlInput = this.url
    }
    this.setupReloadTimer()
  }

  beforeDestroy() {
    this.clearReloadTimer()
  }

  @Watch('reloadTimer')
  onReloadTimerChanged() {
    this.setupReloadTimer()
  }

  @Watch('url')
  onUrlChanged(newUrl: string) {
    if (newUrl) {
      this.urlInput = newUrl
    }
  }

  submitUrl() {
    this.$store.dispatch(`${this.paneId}/setUrl`, this.urlInput)
    this.editing = false
  }

  reload() {
    this.iframeKey++
  }

  toggleInteractive() {
    this.$store.commit(`${this.paneId}/TOGGLE_INTERACTIVE`)
  }

  unlockUrl() {
    this.$store.commit(`${this.paneId}/UNLOCK_URL`)
  }

  setupReloadTimer() {
    this.clearReloadTimer()

    if (this.reloadTimer && this.reloadTimer > 0) {
      this._reloadInterval = window.setInterval(() => {
        this.reload()
      }, this.reloadTimer * 1000)
    }
  }

  clearReloadTimer() {
    if (this._reloadInterval) {
      clearInterval(this._reloadInterval)
      this._reloadInterval = null
    }
  }
}
</script>

<style lang="scss" scoped>
.pane-website {
  width: 100%;
  height: 100%;
  position: relative;
  display: flex;
  flex-direction: column;

  &__header {
    background: 0;
  }

  &__input {
    padding: 0.5rem;
    z-index: 1;

    .form-control {
      width: 100%;
      border: 0;
      font-size: 1em;
      padding: 0.5em;
    }
  }

  &__iframe {
    flex: 1;
    width: 100%;
    border: 0;
    pointer-events: none;

    &.-interactive {
      pointer-events: auto;
    }

    &.-invert {
      filter: invert(1);
    }
  }

  &__empty {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    opacity: 0.5;
  }
}
</style>
