// Aguarda a página carregar e então remove o preloader e faz fade-in do conteúdo
window.addEventListener('load', function() {
  const preloader = document.getElementById('preloader');
  const content = document.getElementById('content');
  if (preloader) {
    preloader.style.display = 'none';
  }
  if (content) {
    content.style.opacity = '1';
  }

  // PWA: Registro do Service Worker (ajuste a rota conforme necessário)
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker
      .register('/service-worker.js')
      .then(() => console.log('Service Worker registrado com sucesso!'))
      .catch(err => console.error('Falha ao registrar o SW:', err));
  }
});

/* SIDEBAR CONTROLS */
const hamburgerBtn = document.getElementById('hamburgerBtn');
const mobileSidebar = document.getElementById('mobileSidebar');
const overlay = document.getElementById('overlay');

if (hamburgerBtn && mobileSidebar && overlay) {
  hamburgerBtn.addEventListener('click', () => {
    mobileSidebar.classList.toggle('open');
    overlay.classList.toggle('open');
  });

  overlay.addEventListener('click', () => {
    mobileSidebar.classList.remove('open');
    overlay.classList.remove('open');
  });
}

/* MODAL MANUAL */
function openManualModal() {
  document.getElementById('manualModal').style.display = 'flex';
}
function closeManualModal() {
  document.getElementById('manualModal').style.display = 'none';
}

/* MODAL DE CATEGORIAS (3 passos) */
// Variáveis de controle dos passos
let currentStep = 1; // 1 = categoria principal, 2 = subcategoria, 3 = marca

function openCategoryModal() {
  document.getElementById('categoryModal').style.display = 'flex';
  // Começa sempre no passo 1
  currentStep = 1;
  resetCategoryModalSteps();
  showMainCategories();

  // Botão "Voltar" não deve aparecer no passo 1
  const backBtn = document.getElementById('backButton');
  if (backBtn) {
    backBtn.style.display = 'none'; // esconde no início
  }
}

function closeCategoryModal() {
  document.getElementById('categoryModal').style.display = 'none';
  resetCategoryModalSteps();
}

// Função para voltar um passo
function goBackOneStep() {
  if (currentStep === 2) {
    // Se estiver na subcategoria, volta para as categorias principais
    currentStep = 1;
    document.getElementById('mainCategoryStep').style.display = 'block';
    document.getElementById('subCategoryStep').style.display = 'none';
    document.getElementById('brandStep').style.display = 'none';
    window.selectedMainCatIndex = undefined;
    window.selectedSubCatIndex = undefined;

    // Passo 1 -> Esconde o botão "Voltar"
    const backBtn = document.getElementById('backButton');
    if (backBtn) {
      backBtn.style.display = 'none';
    }

  } else if (currentStep === 3) {
    // Se estiver na tela de marcas, volta para a subcategoria
    currentStep = 2;
    document.getElementById('mainCategoryStep').style.display = 'none';
    document.getElementById('subCategoryStep').style.display = 'block';
    document.getElementById('brandStep').style.display = 'none';
    window.selectedSubCatIndex = undefined;

    // Passo 2 -> Mostra o botão "Voltar"
    const backBtn = document.getElementById('backButton');
    if (backBtn) {
      backBtn.style.display = 'inline-block';
    }

  } else {
    // Se estiver no primeiro passo, fecha o modal
    closeCategoryModal();
  }
}

function resetCategoryModalSteps() {
  document.getElementById('mainCategoryStep').style.display = 'block';
  document.getElementById('subCategoryStep').style.display = 'none';
  document.getElementById('brandStep').style.display = 'none';

  // Limpa seleções
  window.selectedMainCatIndex = undefined;
  window.selectedSubCatIndex = undefined;
}

// Exemplo de dados de categorias, subcategorias e marcas
const categoryData = [
  {
    name: "Veículos",
    img: "carro_icon.webp",
    subCategories: [
      {
        name: "Carros",
        img: "carro_icon.webp",
        brands: ["Toyota", "Honda", "Ford", "Fiat", "Volkswagen", "Peugeot", "Chevrolet"]
      },
      {
        name: "Motos",
        img: "motos_icon.webp",
        brands: ["Yamaha", "Honda", "Harley-Davidson", "Suzuki", "BMW"]
      },
      {
        name: "Caminhonetes",
        img: "caminhonete_icon.webp",
        brands: ["Toyota", "Chevrolet", "Ford", "Mitsubishi", "Nissan"]
      },
      {
        name: "Caminhões",
        img: "caminhoes_icon.webp",
        brands: ["Mercedes-Benz", "Volvo", "Scania", "Iveco"]
      },
      {
        name: "Ônibus",
        img: "onibus_icon.webp",
        brands: ["Marcopolo", "Volvo", "Mercedes-Benz"]
      }
    ]
  },
  {
    name: "Máquinas Agrícolas",
    img: "tratores_icon.webp",
    subCategories: [
      {
        name: "Tratores",
        img: "tratores_icon.webp",
        brands: ["John Deere", "Massey Ferguson", "Valtra/Valmet", "New Holland", "Case"]
      },
      {
        name: "Colheitadeiras",
        img: "colheitadeira_icon.webp",
        brands: ["John Deere", "Case", "New Holland"]
      },
      {
        name: "Plantadeiras e Pulverizadores",
        img: "plantadeiras_e_pulverizadores_icon.webp",
        brands: ["Stara", "Jacto", "Kuhn"]
      }
    ]
  },
  {
    name: "Equipamentos Industriais",
    img: "empilhadeira_icon.webp",
    subCategories: [
      {
        name: "Motores e Geradores",
        img: "motores_geradores_icon.webp",
        brands: ["Cummins", "Perkins", "Caterpillar"]
      },
      {
        name: "Máquinas Pesadas",
        img: "maquinas_pesadas_icon.webp",
        brands: ["Caterpillar", "Komatsu", "Volvo"]
      },
      {
        name: "Empilhadeiras e Guinchos",
        img: "empilhadeira_icon.webp",
        brands: []
      }
    ]
  },
  {
    name: "Eletrônicos e Tecnologia",
    img: "celular_icon.webp",
    subCategories: [
      {
        name: "Celulares e Tablets",
        img: "celular_icon.webp",
        brands: ["Apple", "Samsung", "Xiaomi", "Motorola"]
      },
      {
        name: "Notebooks e PCs",
        img: "notebook_icon.webp",
        brands: ["Dell", "Lenovo", "HP", "ASUS", "Acer"]
      },
      {
        name: "Impressoras e Periféricos",
        img: "impressoras_perifericos_icon.webp",
        brands: []
      },
      {
        name: "Consoles e Videogames",
        img: "controle_icon.webp",
        brands: []
      },
      {
        name: "Televisores e Acessórios",
        img: "televisores_e_acessorios_icon.webp",
        brands: ["LG", "Samsung", "Sony", "Philips", "TCL", "Panasonic"]
      }
    ]
  },
  {
    name: "Sistemas Hidráulicos e Pneumáticos",
    img: "compressores_de_ar_icon.webp",
    subCategories: [
      {
        name: "Bombas Hidráulicas e Pneumáticas",
        img: "bomba_hidraulica_icon.webp",
        brands: []
      },
      {
        name: "Compressores de Ar",
        img: "compressores_de_ar_icon.webp",
        brands: []
      },
      {
        name: "Cilindros Hidráulicos",
        img: "cilindro_hidraulico_icon.webp",
        brands: []
      }
    ]
  },
  {
    name: "Eletrodomésticos e Equipamentos Domésticos",
    img: "microondas_icon.webp",
    subCategories: [
      {
        name: "Geladeiras e Freezers",
        img: "geladeira_freezer_icon.webp",
        brands: []
      },
      {
        name: "Máquinas de Lavar e Secadoras",
        img: "maquina_de_lavar_e_secadora_icon.webp",
        brands: []
      },
      {
        name: "Ar-condicionado",
        img: "ar_condicionado_icon.webp",
        brands: []
      },
      {
        name: "Cafeteiras e Eletroportáteis",
        img: "cafeteiras_e_eletroportateis_icon.webp",
        brands: ["Mondial", "Nespresso", "Dolce Gusto", "Oster", "Cadence", "Britânia"]
      }
    ]
  },
  {
    name: "Ferramentas e Manutenção Geral",
    img: "ferramentas_icon.webp",
    subCategories: [
      {
        name: "Furadeiras, Parafusadeiras e Esmerilhadeiras",
        img: "furadeira_parafusadeira_esmerilhadeira_icon.webp",
        brands: []
      },
      {
        name: "Equipamentos de Solda e Corte",
        img: "equipamentos_solda_e_corte_icon.webp",
        brands: []
      }
    ]
  }
];

// Exibir categorias principais
function showMainCategories() {
  const container = document.getElementById('mainCategoryContainer');
  if (!container) return;
  container.innerHTML = '';

  categoryData.forEach((cat, idx) => {
    const btn = document.createElement('button');
    btn.className = 'btn-categorias';
    btn.innerHTML = `
      <img src="/static/images/${cat.img}" alt="${cat.name}"
           style="width:60px;height:60px;margin-right:15px;">
      <span>${cat.name}</span>
    `;
    btn.onclick = () => {
      currentStep = 2;
      window.selectedMainCatIndex = idx;
      document.getElementById('mainCategoryStep').style.display = 'none';
      document.getElementById('subCategoryStep').style.display = 'block';
      document.getElementById('brandStep').style.display = 'none';
      showSubCategories(idx);

      // Passo 2 -> Mostra o botão "Voltar"
      const backBtn = document.getElementById('backButton');
      if (backBtn) {
        backBtn.style.display = 'inline-block';
      }
    };
    container.appendChild(btn);
  });
}

// Exibir subcategorias
function showSubCategories(catIndex) {
  const subCatContainer = document.getElementById('subCategoryContainer');
  if (!subCatContainer) return;
  subCatContainer.innerHTML = '';

  const subCats = categoryData[catIndex].subCategories;
  subCats.forEach((sub, subIdx) => {
    const btn = document.createElement('button');
    btn.className = 'btn-categorias';

    if (sub.img) {
      btn.innerHTML = `
        <img src="/static/images/${sub.img}" alt="${sub.name}"
             style="width:60px;height:60px;margin-right:15px;">
        <span>${sub.name}</span>
      `;
    } else {
      btn.textContent = sub.name;
    }

    btn.onclick = () => {
      currentStep = 3;
      window.selectedSubCatIndex = subIdx;
      document.getElementById('mainCategoryStep').style.display = 'none';
      document.getElementById('subCategoryStep').style.display = 'none';
      document.getElementById('brandStep').style.display = 'block';
      showBrands(catIndex, subIdx);

      // Passo 3 -> Botão "Voltar" continua visível
      const backBtn = document.getElementById('backButton');
      if (backBtn) {
        backBtn.style.display = 'inline-block';
      }
    };
    subCatContainer.appendChild(btn);
  });
}

// Exibir marcas
function showBrands(catIndex, subCatIndex) {
  const brandContainer = document.getElementById('brandContainer');
  if (!brandContainer) return;
  brandContainer.innerHTML = '';

  const subCat = categoryData[catIndex].subCategories[subCatIndex];
  const brands = subCat.brands || [];

  // Se não houver marcas definidas, mostrar um botão para ver todos problemas
  if (brands.length === 0) {
    const btnVerProblemas = document.createElement('button');
    btnVerProblemas.className = 'btn-categorias';
    btnVerProblemas.textContent = "Ver problemas desta subcategoria";
    btnVerProblemas.onclick = () => {
      const catName = categoryData[catIndex].name;
      const subCatName = subCat.name;
      window.location.href = `/search?category=${encodeURIComponent(catName)}&subcategory=${encodeURIComponent(subCatName)}`;
      closeCategoryModal();
    };
    brandContainer.appendChild(btnVerProblemas);
    return;
  }

  // Se houver marcas, exibir cada marca como botão
  brands.forEach(brand => {
    let brandName = "";
    let brandImg = null;
    if (typeof brand === 'string') {
      brandName = brand;
    } else {
      brandName = brand.name;
      brandImg = brand.img;
    }

    const btn = document.createElement('button');
    btn.className = 'btn-categorias';

    if (brandImg) {
      btn.innerHTML = `
        <img src="/static/images/${brandImg}" alt="${brandName}"
             style="width:60px;height:60px;margin-right:15px;">
        <span>${brandName}</span>
      `;
    } else {
      btn.textContent = brandName;
    }

    btn.onclick = () => {
      const catName = categoryData[catIndex].name;
      const subCatName = subCat.name;
      window.location.href = `/search?category=${encodeURIComponent(catName)}&subcategory=${encodeURIComponent(subCatName)}&brand=${encodeURIComponent(brandName)}`;
      closeCategoryModal();
    };
    brandContainer.appendChild(btn);
  });

  // Botão "Ver todos problemas desta subcategoria"
  const btnVerTodos = document.createElement('button');
  btnVerTodos.className = 'btn-categorias';
  btnVerTodos.textContent = "Ver todos problemas desta subcategoria";
  btnVerTodos.onclick = () => {
    const catName = categoryData[catIndex].name;
    const subCatName = subCat.name;
    window.location.href = `/search?category=${encodeURIComponent(catName)}&subcategory=${encodeURIComponent(subCatName)}`;
    closeCategoryModal();
  };
  brandContainer.appendChild(btnVerTodos);
}
