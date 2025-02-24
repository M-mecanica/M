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

/* MODAL LOGIN */
function openLoginModal() {
  document.getElementById('loginModal').style.display = 'flex';
}
function closeLoginModal() {
  document.getElementById('loginModal').style.display = 'none';
}

/* MODAL MANUAL */
function openManualModal() {
  document.getElementById('manualModal').style.display = 'flex';
}
function closeManualModal() {
  document.getElementById('manualModal').style.display = 'none';
}

/* MODAL DE CATEGORIAS (3 passos) */
function openCategoryModal() {
  document.querySelector('#categoryModal .modal-header h2').innerText = "Escolha a categoria principal:";
  document.getElementById('categoryModal').style.display = 'flex';
  showMainCategories();
}
function closeCategoryModal() {
  document.getElementById('categoryModal').style.display = 'none';
  resetCategoryModalSteps();
}

// Exemplo de dados de categorias, subcategorias e marcas
const categoryData = [
  {
    name: "Veículos",
    img: "carro_icon.png",
    subCategories: [
      {
        name: "Carros",
        img: "carro_icon.png",
        brands: ["Toyota", "Honda", "Ford", "Fiat", "Volkswagen", "Peugeot", "Chevrolet"]
      },
      {
        name: "Motos",
        img: "moto_icon.png",
        brands: ["Yamaha", "Honda", "Harley-Davidson", "Suzuki", "BMW"]
      },
      {
        name: "Caminhonetes",
        img: "caminhonete_icon.png",
        brands: ["Toyota", "Chevrolet", "Ford", "Mitsubishi", "Nissan"]
      },
      {
        name: "Caminhões",
        img: "caminhao_icon.png",
        brands: ["Mercedes-Benz", "Volvo", "Scania", "Iveco"]
      },
      {
        name: "Ônibus",
        img: "onibus_icon.png",
        brands: ["Marcopolo", "Volvo", "Mercedes-Benz"]
      }
    ]
  },
  {
    name: "Máquinas Agrícolas",
    img: "trator_icon.png",
    subCategories: [
      {
        name: "Tratores",
        img: "trator_icon.png",
        brands: ["John Deere", "Massey Ferguson", "Valtra/Valmet", "New Holland", "Case"]
      },
      {
        name: "Colheitadeiras",
        img: "colheitadeira_icon.png",
        brands: ["John Deere", "Case", "New Holland"]
      },
      {
        name: "Plantadeiras e Pulverizadores",
        img: "plantadeira_icon.png",
        brands: ["Stara", "Jacto", "Kuhn"]
      }
    ]
  },
  {
    name: "Equipamentos Industriais",
    img: "empilhadeira_icon.png",
    subCategories: [
      {
        name: "Motores e Geradores",
        img: "motor_icon.png",
        brands: ["Cummins", "Perkins", "Caterpillar"]
      },
      {
        name: "Máquinas Pesadas",
        img: "escavadeira_icon.png",
        brands: ["Caterpillar", "Komatsu", "Volvo"]
      },
      {
        name: "Empilhadeiras e Guinchos",
        img: "empilhadeira_icon.png",
        brands: []
      }
    ]
  },
  {
    name: "Eletrônicos e Tecnologia",
    img: "celular_icon.png",
    subCategories: [
      {
        name: "Celulares e Tablets",
        img: "celular_icon.png",
        brands: ["Apple", "Samsung", "Xiaomi", "Motorola"]
      },
      {
        name: "Notebooks e PCs",
        img: "notebook_icon.png",
        brands: ["Dell", "Lenovo", "HP", "ASUS", "Acer"]
      },
      {
        name: "Impressoras e Periféricos",
        img: "impressora_icon.png",
        brands: []
      },
      {
        name: "Consoles e Videogames",
        img: "controle_videogame_icon.png",
        brands: []
      },
      {
        name: "Televisores e Acessórios",
        img: "tv_icon.png",
        brands: ["LG", "Samsung", "Sony", "Philips", "TCL", "Panasonic"]
      }
    ]
  },
  {
    name: "Sistemas Hidráulicos e Pneumáticos",
    img: "compressor_de_ar_icon.png",
    subCategories: [
      {
        name: "Bombas Hidráulicas e Pneumáticas",
        img: "bomba_hidraulica_icon.png",
        brands: []
      },
      {
        name: "Compressores de Ar",
        img: "compressor_de_ar_icon.png",
        brands: []
      },
      {
        name: "Cilindros Hidráulicos",
        img: "cilindro_hidraulico_icon.png",
        brands: []
      }
    ]
  },
  {
    name: "Eletrodomésticos e Equipamentos Domésticos",
    img: "microondas_icon.png",
    subCategories: [
      {
        name: "Geladeiras e Freezers",
        img: "geladeira_icon.png",
        brands: []
      },
      {
        name: "Máquinas de Lavar e Secadoras",
        img: "maquina_de_lava_icon.png",
        brands: []
      },
      {
        name: "Ar-condicionado",
        img: "ar_condicionado_icon.png",
        brands: []
      },
      {
        name: "Cafeteiras e Eletroportáteis",
        img: "cafeteira_icon.png",
        brands: ["Mondial", "Nespresso", "Dolce Gusto", "Oster", "Cadence", "Britânia"]
      }
    ]
  },
  {
    name: "Ferramentas e Manutenção Geral",
    img: "ferramentas_icon.png",
    subCategories: [
      {
        name: "Furadeiras, Parafusadeiras e Esmerilhadeiras",
        img: "furadeira_icon.png",
        brands: []
      },
      {
        name: "Equipamentos de Solda e Corte",
        img: "equipamentos_solda_e_corte_icon.png",
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
      document.querySelector('#categoryModal .modal-header h2').innerText = "Escolha a subcategoria";
      document.getElementById('mainCategoryStep').style.display = 'none';
      document.getElementById('subCategoryStep').style.display = 'block';
      document.getElementById('selectedMainCategoryText').innerText = "Categoria selecionada: " + cat.name;
      window.selectedMainCatIndex = idx;
      showSubCategories(idx);
    };
    container.appendChild(btn);
  });
}

// Exibir subcategorias (agora com imagem, se existir)
function showSubCategories(catIndex) {
  const subCatContainer = document.getElementById('subCategoryContainer');
  if (!subCatContainer) return;
  subCatContainer.innerHTML = '';

  const subCats = categoryData[catIndex].subCategories;
  subCats.forEach((sub, subIdx) => {
    const btn = document.createElement('button');
    btn.className = 'btn-categorias';

    // Se a subcategoria tiver imagem definida
    if (sub.img) {
      btn.innerHTML = `
        <img src="/static/images/${sub.img}" alt="${sub.name}"
             style="width:60px;height:60px;margin-right:15px;">
        <span>${sub.name}</span>
      `;
    } else {
      // Se não tiver imagem, só texto
      btn.textContent = sub.name;
    }

    btn.onclick = () => {
      document.getElementById('subCategoryStep').style.display = 'none';
      document.getElementById('brandStep').style.display = 'block';
      document.querySelector('#categoryModal .modal-header h2').innerText = "Escolha a marca:";
      document.getElementById('selectedSubCategoryText').innerText = "Subcategoria selecionada: " + sub.name;
      window.selectedSubCatIndex = subIdx;
      showBrands(catIndex, subIdx);
    };
    subCatContainer.appendChild(btn);
  });
}

// Exibir marcas (aceitando tanto strings quanto objetos {name, img})
function showBrands(catIndex, subCatIndex) {
  const brandContainer = document.getElementById('brandContainer');
  if (!brandContainer) return;
  brandContainer.innerHTML = '';

  const subCat = categoryData[catIndex].subCategories[subCatIndex];
  const brands = subCat.brands || [];

  // Se não houver marcas cadastradas (array vazio), só mostra "Ver problemas"
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

  // Se houver marcas, exibe cada uma
  brands.forEach(brand => {
    let brandName = "";
    let brandImg = null;
    if (typeof brand === 'string') {
      // Se for apenas string, sem ícone
      brandName = brand;
    } else {
      // Caso queira implementar objetos de marca com name e img
      brandName = brand.name;
      brandImg = brand.img;
    }

    const btn = document.createElement('button');
    btn.className = 'btn-categorias';

    // Se houver imagem de marca, renderiza
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

  // Botão para "Ver todos problemas desta subcategoria"
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

// Voltar para a lista de categorias principais
function goBackToMainCategory() {
  document.querySelector('#categoryModal .modal-header h2').innerText = "Escolha a categoria principal:";
  document.getElementById('subCategoryStep').style.display = 'none';
  document.getElementById('mainCategoryStep').style.display = 'block';
}

// Voltar para a lista de subcategorias
function goBackToSubCategory() {
  document.querySelector('#categoryModal .modal-header h2').innerText = "Escolha a subcategoria";
  document.getElementById('brandStep').style.display = 'none';
  document.getElementById('subCategoryStep').style.display = 'block';
}

// Resetar o modal para o passo inicial
function resetCategoryModalSteps() {
  document.getElementById('mainCategoryStep').style.display = 'block';
  document.getElementById('subCategoryStep').style.display = 'none';
  document.getElementById('brandStep').style.display = 'none';
}
