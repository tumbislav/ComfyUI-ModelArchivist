<script lang=ts>
    let { children } = $props();
</script>

<svelte:head>
    <link href="/css/archivist.css" rel="stylesheet"/>
    <link href="/css/controls.css" rel="stylesheet"/>
    <link href="/css/tags.css" rel="stylesheet"/>
    <link href="archivist-ico-32.png" rel="icon"/>
    <link href="/css/fontawesome.min.css" rel="stylesheet"/>
    <link href="/css/solid.min.css" rel="stylesheet"/>
    <link href="/webfonts/fa-solid-900.woff2" rel="preload" as="font" type="font/woff2">
</svelte:head>

{@render children()}
