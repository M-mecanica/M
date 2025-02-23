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
    img: "Carro icon.PNG",
    subCategories: [
      {
        name: "Carros",
        brands: [
          { name: "Toyota", img: "Toyota icon.PNG" },
          { name: "Honda", img: "Honda icon.PNG" },
          { name: "Ford",  img: "Ford icon.PNG" },
          { name: "Fiat",  img: "Fiat icon.PNG" },
          { name: "Volkswagen", img: "Volkswagen icon.PNG" },
          { name: "Peugeot", img: "Peugeot icon.PNG" },
          { name: "Chevrolet", img: "Chevrolet icon.PNG" }
        ]
      },
      {
        name: "Motos",
        brands: [
          { name: "Yamaha", img: "Yamaha icon.PNG" },
          { name: "Honda",  img: "Honda icon.PNG" },
          { name: "Harley-Davidson", img: "Harley icon.PNG" },
          { name: "Suzuki", img: "Suzuki icon.PNG" },
          { name: "BMW",    img: "BMW icon.PNG" }
        ]
      },
      {
        name: "Caminhonetes",
        brands: [
          { name: "Toyota Hilux",   img: "ToyotaHilux icon.PNG" },
          { name: "Chevrolet S10",  img: "ChevroletS10 icon.PNG" },
          { name: "Ford Ranger",    img: "FordRanger icon.PNG" },
          { name: "Mitsubishi L200", img: "MitsubishiL200 icon.PNG" },
          { name: "Nissan Frontier", img: "NissanFrontier icon.PNG" }
        ]
      },
      {
        name: "Caminhões",
        brands: [
          { name: "Mercedes-Benz", img: "Mercedes icon.PNG" },
          { name: "Volvo",         img: "Volvo icon.PNG" },
          { name: "Scania",        img: "Scania icon.PNG" },
          { name: "Iveco",         img: "Iveco icon.PNG" }
        ]
      },
      {
        name: "Ônibus",
        brands: [
          { name: "Marcopolo",  img: "Marcopolo icon.PNG" },
          { name: "Volvo",      img: "Volvo icon.PNG" },
          { name: "Mercedes-Benz", img: "Mercedes icon.PNG" }
        ]
      }
    ]
  },
  {
    name: "Máquinas Agrícolas",
    img: "Trator icon.PNG",
    subCategories: [
      {
        name: "Tratores",
        brands: ["John Deere", "Massey Ferguson", "Valtra/Valmet", "New Holland", "Case"]
      },
      {
        name: "Colheitadeiras",
        brands: ["John Deere", "Case IH", "New Holland"]
      },
      {
        name: "Plantadeiras e Pulverizadores",
        brands: ["Stara", "Jacto", "Kuhn"]
      }
    ]
  },
  {
    name: "Equipamentos Industriais",
    img: "Empilhadeira icon.PNG",
    subCategories: [
      {
        name: "Motores e Geradores",
        brands: ["Cummins", "Perkins", "Caterpillar"]
      },
      {
        name: "Máquinas Pesadas",
        brands: ["Caterpillar", "Komatsu", "Volvo"]
      },
      {
        name: "Empilhadeiras e Guinchos",
        brands: []
      }
    ]
  },
  {
    name: "Eletrônicos e Tecnologia",
    img: "Celular icon.PNG",
    subCategories: [
      {
        name: "Celulares e Tablets",
        brands: ["Apple", "Samsung", "Xiaomi", "Motorola"]
      },
      {
        name: "Notebooks e PCs",
        brands: ["Dell", "Lenovo", "HP", "ASUS", "Acer"]
      },
      {
        name: "Impressoras e Periféricos",
        brands: []
      },
      {
        name: "Consoles e Videogames",
        brands: []
      },
      {
        name: "Televisores e Acessórios",
        brands: ["LG", "Samsung", "Sony", "Philips", "TCL", "Panasonic"]
      }
    ]
  },
  {
    name: "Sistemas Hidráulicos e Pneumáticos",
    img: "Compressor de ar icon.PNG",
    subCategories: [
      {
        name: "Bombas Hidráulicas e Pneumáticas",
        brands: []
      },
      {
        name: "Compressores de Ar",
        brands: []
      },
      {
        name: "Cilindros Hidráulicos",
        brands: []
      }
    ]
  },
  {
    name: "Eletrodomésticos e Equipamentos Domésticos",
    img: "Microondas icon.PNG",
    subCategories: [
      {
        name: "Geladeiras e Freezers",
        brands: []
      },
      {
        name: "Máquinas de Lavar e Secadoras",
        brands: []
      },
      {
        name: "Ares-condicionados",
        brands: []
      },
      {
        name: "Cafeteiras e Eletroportáteis",
        brands: ["Mondial", "Nespresso", "Dolce Gusto", "Oster", "Cadence", "Britânia"]
      }
    ]
  },
  {
    name: "Ferramentas e Manutenção Geral",
    img: "Ferramentas icon.PNG",
    subCategories: [
      {
        name: "Furadeiras, Parafusadeiras e Esmerilhadeiras",
        brands: []
      },
      {
        name: "Compressores e Ferramentas Pneumáticas",
        brands: []
      },
      {
        name: "Equipamentos de Solda e Corte",
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

// Exibir subcategorias
function showSubCategories(catIndex) {
  const subCatContainer = document.getElementById('subCategoryContainer');
  if (!subCatContainer) return;
  subCatContainer.innerHTML = '';

  const subCats = categoryData[catIndex].subCategories;
  subCats.forEach((sub, subIdx) => {
    const btn = document.createElement('button');
    btn.className = 'btn-categorias';
    btn.textContent = sub.name;
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
