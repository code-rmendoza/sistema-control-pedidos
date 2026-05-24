(function () {
  const form = document.querySelector("[data-order-form]");
  if (!form) {
    return;
  }

  const money = new Intl.NumberFormat("es-VE", {
    style: "currency",
    currency: "USD",
  });

  const numberFrom = (input) => {
    if (!input || !input.value) {
      return 0;
    }
    const value = Number(String(input.value).replace(",", "."));
    return Number.isFinite(value) ? value : 0;
  };

  const setAll = (selector, value) => {
    document.querySelectorAll(selector).forEach((node) => {
      node.textContent = value;
    });
  };

  const extractImageUrl = (value) => {
    const text = value.trim();
    if (!text) {
      return "";
    }
    const attrMatch = text.match(/\bsrc\s*=\s*["']([^"']+)["']/i);
    if (attrMatch) {
      return attrMatch[1];
    }
    const urlMatch = text.match(/https?:\/\/[^\s"'<>]+?\.(?:jpg|jpeg|png|webp)(?:\?[^\s"'<>]*)?/i);
    if (urlMatch) {
      return urlMatch[0];
    }
    const protocolRelativeMatch = text.match(/\/\/[^\s"'<>]+?\.(?:jpg|jpeg|png|webp)(?:\?[^\s"'<>]*)?/i);
    if (protocolRelativeMatch) {
      return `https:${protocolRelativeMatch[0]}`;
    }
    return text;
  };

  const replaceIndex = (value, oldIndex, newIndex) => {
    if (!value) {
      return value;
    }
    return value.replace(new RegExp(`-${oldIndex}-`, "g"), `-${newIndex}-`);
  };

  const clearCloneValues = (clone) => {
    clone.querySelectorAll("input, textarea, select").forEach((field) => {
      if (field.type === "hidden" && field.name && field.name.endsWith("-id")) {
        field.value = "";
        return;
      }
      if (field.type === "checkbox" || field.type === "radio") {
        field.checked = false;
        return;
      }
      if (field.tagName === "SELECT") {
        field.selectedIndex = 0;
        return;
      }
      if (field.type !== "hidden") {
        field.value = "";
      }
    });
  };

  const renumberClone = (clone, oldIndex, newIndex) => {
    clone.querySelectorAll("[name]").forEach((node) => {
      node.name = replaceIndex(node.name, oldIndex, newIndex);
    });
    clone.querySelectorAll("[id]").forEach((node) => {
      node.id = replaceIndex(node.id, oldIndex, newIndex);
    });
    clone.querySelectorAll("label[for]").forEach((node) => {
      node.setAttribute("for", replaceIndex(node.getAttribute("for"), oldIndex, newIndex));
    });
  };

  const addProduct = () => {
    const totalForms = form.querySelector('input[name$="-TOTAL_FORMS"]');
    const itemsWrap = form.querySelector(".order-items");
    const template = itemsWrap && itemsWrap.querySelector("[data-order-item]:last-child");
    if (!totalForms || !itemsWrap || !template) {
      return;
    }

    const oldIndex = Number(totalForms.value) - 1;
    const newIndex = Number(totalForms.value);
    const clone = template.cloneNode(true);
    renumberClone(clone, oldIndex, newIndex);
    clearCloneValues(clone);
    clone.classList.remove("is-deleted");

    const productNumber = clone.querySelector(".order-item-card__head span");
    const title = clone.querySelector("[data-item-title]");
    const preview = clone.querySelector("[data-image-preview]");
    if (productNumber) {
      productNumber.textContent = `Producto ${newIndex + 1}`;
    }
    if (title) {
      title.textContent = "Nuevo producto";
    }
    if (preview) {
      preview.dataset.initialImage = "";
      preview.innerHTML = "<span>Sin imagen</span>";
    }

    itemsWrap.appendChild(clone);
    totalForms.value = String(newIndex + 1);
    update();
  };

  const setFetchStatus = (item, message, type) => {
    const status = item.querySelector("[data-fetch-status]");
    if (!status) {
      return;
    }
    status.textContent = message || "";
    status.classList.toggle("is-error", type === "error");
    status.classList.toggle("is-ok", type === "ok");
  };

  const fetchProductImage = async (button) => {
    const item = button.closest("[data-order-item]");
    const endpoint = form.dataset.imageFetchUrl;
    const linkInput = item && item.querySelector('input[name$="-link"]');
    const imageUrlInput = item && item.querySelector('input[name$="-imagen_url"]');
    const productUrl = linkInput && linkInput.value.trim();
    if (!item || !endpoint || !imageUrlInput) {
      return;
    }
    if (!productUrl) {
      setFetchStatus(item, "Coloca primero el link del producto.", "error");
      return;
    }

    button.disabled = true;
    const originalText = button.textContent;
    button.textContent = "Buscando...";
    setFetchStatus(item, "Leyendo pagina del producto...", "");

    try {
      const response = await fetch(`${endpoint}?url=${encodeURIComponent(productUrl)}`, {
        headers: { "Accept": "application/json" },
      });
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        throw new Error(payload.error || "No se pudo traer la imagen.");
      }
      imageUrlInput.value = payload.image_url;
      imageUrlInput.dispatchEvent(new Event("input", { bubbles: true }));
      setFetchStatus(item, "Imagen encontrada.", "ok");
      updatePreview(item);
    } catch (error) {
      setFetchStatus(item, error.message, "error");
    } finally {
      button.disabled = false;
      button.textContent = originalText;
    }
  };

  const updatePreview = (item) => {
    const preview = item.querySelector("[data-image-preview]");
    const fileInput = item.querySelector('input[type="file"][name$="-imagen"]');
    const urlInput = item.querySelector('input[name$="-imagen_url"]');
    if (!preview) {
      return;
    }

    const renderImage = (src) => {
      preview.innerHTML = "";
      const image = document.createElement("img");
      image.src = src;
      image.alt = "Preview del producto";
      preview.appendChild(image);
    };

    if (fileInput && fileInput.files && fileInput.files[0]) {
      renderImage(URL.createObjectURL(fileInput.files[0]));
      return;
    }

    if (urlInput && urlInput.value) {
      const cleanUrl = extractImageUrl(urlInput.value);
      if (cleanUrl !== urlInput.value) {
        urlInput.value = cleanUrl;
      }
      renderImage(cleanUrl);
      return;
    }

    if (preview.dataset.initialImage) {
      renderImage(preview.dataset.initialImage);
      return;
    }

    preview.innerHTML = "<span>Sin imagen</span>";
  };

  const update = () => {
    let total = 0;
    let cost = 0;
    let count = 0;

    document.querySelectorAll("[data-order-item]").forEach((item) => {
      const deleted = item.querySelector('input[name$="-DELETE"]');
      const isDeleted = deleted && deleted.checked;
      item.classList.toggle("is-deleted", Boolean(isDeleted));

      const title = item.querySelector("[data-item-title]");
      const description = item.querySelector('input[name$="-descripcion"]');
      if (title && description && description.value.trim()) {
        title.textContent = description.value.trim();
      }

      updatePreview(item);

      const price = numberFrom(item.querySelector('input[name$="-precio_final"]'));
      const estimatedCost = numberFrom(item.querySelector('input[name$="-costo_estimado"]'));
      const realCostInput = item.querySelector('input[name$="-costo_real"]');
      const hasRealCost = Boolean(realCostInput && realCostInput.value.trim());
      const usedCost = hasRealCost ? numberFrom(realCostInput) : estimatedCost;
      const profit = price - usedCost;
      const profitNode = item.querySelector("[data-item-profit]");
      const profitLabel = item.querySelector("[data-item-profit-label]");
      if (profitNode) {
        profitNode.textContent = money.format(profit);
      }
      if (profitLabel) {
        profitLabel.textContent = hasRealCost ? "Ganancia real" : "Ganancia estimada";
      }

      if (!isDeleted && (description && description.value.trim())) {
        total += price;
        cost += usedCost;
        count += 1;
      }
    });

    const initial = total * 0.5;
    setAll("[data-order-total]", money.format(total));
    setAll("[data-order-cost]", money.format(cost));
    setAll("[data-order-profit]", money.format(total - cost));
    setAll("[data-order-initial]", money.format(initial));
    setAll("[data-order-count]", String(count));
  };

  form.addEventListener("input", update);
  form.addEventListener("change", update);
  form.addEventListener("click", (event) => {
    const button = event.target.closest("[data-fetch-product-image]");
    if (button) {
      fetchProductImage(button);
    }
  });
  document.querySelector("[data-add-product]")?.addEventListener("click", addProduct);
  update();
})();
