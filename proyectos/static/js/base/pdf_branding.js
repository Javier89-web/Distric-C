(function () {
    "use strict";

    const assets = {
        utc: null,
        distric: null
    };

    function blobToDataUrl(blob) {
        return new Promise(function (resolve, reject) {
            const reader = new FileReader();
            reader.onload = function () { resolve(reader.result); };
            reader.onerror = reject;
            reader.readAsDataURL(blob);
        });
    }

    async function cargarImagen(url) {
        try {
            const response = await fetch(url, { cache: "force-cache" });
            if (!response.ok) return null;
            return await blobToDataUrl(await response.blob());
        } catch (error) {
            return null;
        }
    }

    Promise.all([
        cargarImagen("/static/img/branding/utc-logo.png"),
        cargarImagen("/static/img/branding/distric-c-logo.png")
    ]).then(function (resultados) {
        assets.utc = resultados[0];
        assets.distric = resultados[1];
    });

    function aplicar(doc, titulo) {
        if (!doc) return;
        const tituloFinal = titulo || "Distri C";

        doc.pageMargins = [34, 58, 34, 38];

        if (assets.utc) {
            doc.background = function (currentPage, pageSize) {
                const ancho = Math.min(112, pageSize.width * 0.20);
                const alto = ancho * (224 / 497);
                return {
                    image: assets.utc,
                    width: ancho,
                    opacity: 0.085,
                    absolutePosition: {
                        x: 28,
                        y: pageSize.height - alto - 18
                    }
                };
            };
        }

        doc.header = function () {
            const columnas = [];
            if (assets.distric) {
                columnas.push({ image: assets.distric, width: 72, margin: [0, 0, 8, 0] });
            }
            columnas.push({
                text: tituloFinal,
                bold: true,
                fontSize: 9,
                color: "#23262b",
                alignment: "center",
                margin: [0, 7, 0, 0]
            });
            if (assets.utc) {
                columnas.push({ image: assets.utc, width: 78, margin: [8, 2, 0, 0] });
            }
            return { columns: columnas, margin: [34, 12, 34, 0] };
        };

        doc.footer = function (currentPage, pageCount) {
            return {
                columns: [
                    { text: "Universidad Técnica de Cotopaxi · Distri C", fontSize: 7, color: "#6b7280" },
                    { text: `Página ${currentPage} de ${pageCount}`, alignment: "right", fontSize: 7, color: "#6b7280" }
                ],
                margin: [34, 0, 34, 14]
            };
        };
    }

    window.DistricPdfBranding = {
        apply: aplicar,
        isReady: function () { return Boolean(assets.utc || assets.distric); }
    };
})();
